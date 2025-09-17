from bs4 import BeautifulSoup
import re
import cloudscraper
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Initialize the scraper that can handle Cloudflare
scraper = cloudscraper.create_scraper()

# Thread-safe list to store results
drama_data_list = []
data_lock = threading.Lock()

# ==============================================================================
# HELPER AND PARSING FUNCTIONS
# ==============================================================================

def get_scrape_urls_from_page(html):
    """Finds all individual show/movie URLs from a top-250 list page."""
    soup = BeautifulSoup(html, "html.parser")
    base_url = "https://mydramalist.com"
    scrape_urls = []
    all_urls_on_page = soup.find_all('h6', class_='text-primary title')
    for heading in all_urls_on_page:
        link_tag = heading.find('a')
        if link_tag and link_tag.has_attr('href'):
            relative_url = link_tag['href']
            full_url = base_url + relative_url
            scrape_urls.append(full_url)
    return scrape_urls

def get_info_by_label(soup, label):
    """A helper function to find data next to a label like 'Country:'."""
    label_tag = soup.find('b', string=re.compile(r'\s*' + re.escape(label) + r'\s*'))
    if label_tag:
        next_a = label_tag.find_next_sibling('a')
        if next_a:
            return next_a.text.strip()
        next_text = label_tag.next_sibling
        if next_text and isinstance(next_text, str):
            return next_text.strip()
    return None

def extract_drama_details_generic(html_source):
    """Parses an individual drama/movie page to get its details."""
    soup = BeautifulSoup(html_source, 'lxml')
    details = {}
    try:
        details['Name'] = soup.find('h1', class_='film-title').text.strip()
        details['rating'] = soup.find('div', class_='col-film-rating').find('div').text.strip()
        img_tag = soup.find('img', attrs={'itempropx': 'image'})
        print(img_tag['src'])
        details['url'] = img_tag['src']
        

        
        # --- Number of Raters ---
        ratings_div = soup.find('div', class_='hfs', attrs={'itempropx': 'aggregateRating'})
        if ratings_div:
            ratings_text = ratings_div.text
            # Extract number from "Ratings: 9.2/10 from 22,605 users"
            raters_match = re.search(r'from\s+([0-9,]+)\s+users', ratings_text)
            if raters_match:
                details['num_raters'] = raters_match.group(1).replace(',', '')
            else:
                details['num_raters'] = None
        else:
            details['num_raters'] = None
        
        main_details_area = soup.find('div', class_='show-detailsxss')
        if main_details_area:
            genre_list = main_details_area.find('li', class_='show-genres')
            details['genre_names'] = [a.text for a in genre_list.find_all('a')] if genre_list else []
            tag_list = main_details_area.find('li', class_='show-tags')
            details['tag_names'] = [a.text for a in tag_list.find_all('a', class_='text-primary')] if tag_list else []

        sidebar_details_area = soup.find('div', class_='box-body light-b')
        if sidebar_details_area:
            details['category'] = get_info_by_label(sidebar_details_area, 'Type:')
            type_li = sidebar_details_area.find("b", string="Type:")
            if type_li:
                parent_li = type_li.find_parent("li")
                if parent_li:
                    span = parent_li.find("span")
                    if span:
                        type_value = span.get_text(strip=True)
                        details['category'] = type_value
            details['country'] = get_info_by_label(sidebar_details_area, 'Country:')
            details['num_episodes'] = get_info_by_label(sidebar_details_area, 'Episodes:')
            details['aired'] = get_info_by_label(sidebar_details_area, 'Aired:')
            details['original_network'] = get_info_by_label(sidebar_details_area, 'Original Network:')
            details['duration'] = get_info_by_label(sidebar_details_area, 'Duration:')
                    
        # --- Director ---
        director_b = soup.find("b", string="Director:")
        director_name = None
        if director_b:
            director_li = director_b.find_parent("li")
            director_tag = director_li.find("a") if director_li else None
            if director_tag:
                director_name = director_tag.get_text(strip=True)
        details['director'] = director_name
        # --- Screenwriters ---
        screenwriter_b = soup.find("b", string="Screenwriter:")
        screenwriters_str = None
        if screenwriter_b:
            screenwriter_li = screenwriter_b.find_parent("li")
            if screenwriter_li:
                screenwriter_tags = screenwriter_li.find_all("a", class_="text-primary")
                screenwriters = [a.get_text(strip=True) for a in screenwriter_tags]
                screenwriters_str = ", ".join(screenwriters)
        details['screenwriter'] = screenwriters_str
        # --- Ratings & Watchers ---
        num_watchers = None
        rating_value = None
        for div in soup.find_all("div", class_="hfs"):
            text = div.get_text(" ", strip=True)
            # rating
            rating_tag = div.find("b", attrs={"itempropx": "ratingValue"})
            if rating_tag:
                rating_value = float(rating_tag.get_text(strip=True))
            # watchers
            match = re.search(r"from\s+(\d+)\s+users", text)
            if match:
                num_watchers = int(match.group(1))
                break  # only one div has the watchers
        details['num_raters'] = num_watchers
        # --- Synopsis ---
        synopsis_div = soup.find('div', class_='show-synopsis')
        if synopsis_div:
            # Get text and clean it up
            synopsis_text = synopsis_div.get_text(strip=True)
            details['synopsis'] = synopsis_text if synopsis_text else None
        else:
            details['synopsis'] = None

        # --- Cast (UPDATED based on your 'title' attribute suggestion) ---
        cast_header = soup.find_all('a', class_='text-primary text-ellipsis')
        # Extract all titles from the list of <a> tags
        titles = [a['title'] for a in cast_header if a.has_attr('title')]
        # Join them with commas
        joined_titles = ', '.join(titles)
        details['cast_names'] = joined_titles

    except AttributeError as e:
        print(f"A parsing error occurred: {e}. Some data may be missing.")
        
    return details

def scrape_single_url(drama_url, index, total):
    """Function to scrape a single URL - used by threads."""
    print(f"[{index+1}/{total}] Scraping: {drama_url}")
    try:
        # Create a new scraper instance for each thread to avoid conflicts
        thread_scraper = cloudscraper.create_scraper()
        resp = thread_scraper.get(drama_url)
        if resp.status_code == 200:
            details = extract_drama_details_generic(resp.text)
            print("********\n",details,"\n**********")
            for key, value in details.items():
                if isinstance(value, list):
                    details[key] = ', '.join(value)
            
            # Thread-safe addition to the list
            with data_lock:
                drama_data_list.append(details)
                
            return f"Success: {drama_url}"
        else:
            return f"Failed to fetch {drama_url}: {resp.status_code}"
    except Exception as e:
        return f"Error scraping {drama_url}: {e}"

def process_urls_in_batches(all_urls, max_workers=50, batch_size=500):
    """Process URLs in batches to avoid overwhelming the system."""
    total_urls = len(all_urls)
    processed = 0
    
    # Process URLs in batches
    for i in range(0, total_urls, batch_size):
        batch = all_urls[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_urls + batch_size - 1) // batch_size
        
        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} URLs)...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(scrape_single_url, url, processed + j, total_urls): url 
                for j, url in enumerate(batch)
            }
            
            batch_completed = 0
            for future in as_completed(future_to_url):
                batch_completed += 1
                processed += 1
                result = future.result()
                print(f"[Batch {batch_num}] [{batch_completed}/{len(batch)}] [Total: {processed}/{total_urls}] {result}")
        
        # Small delay between batches to be respectful to the server
        if i + batch_size < total_urls:
            print(f"Batch {batch_num} complete. Waiting 2 seconds before next batch...")
            time.sleep(2)

# ==============================================================================
# MAIN EXECUTION LOGIC
# ==============================================================================

def main():
    """Main function to run the scraper."""
    base_urls = [
        "https://mydramalist.com/shows/top?page={}",
        "https://mydramalist.com/movies/top?page={}"
    ]
    all_scrape_urls = set()

    print("PHASE 1: Collecting all URLs...")
    for base in base_urls:
        for num in range(1, 251):
            url = base.format(num)
            print(f"Fetching URLs from: {url}")
            try:
                response = scraper.get(url)
                if response.status_code == 200:
                    page_urls = get_scrape_urls_from_page(response.text)
                    all_scrape_urls.update(page_urls)
                else:
                    print(f"Failed to retrieve page {url}. Status code: {response.status_code}")
            except Exception as e:
                print(f"An error occurred while fetching {url}: {e}")

    all_scrape_urls = list(all_scrape_urls)
    print(f"\nPHASE 1 COMPLETE: Collected {len(all_scrape_urls)} unique URLs.\n")

    print("PHASE 2: Scraping details for each URL using batch processing...")
    
    # Process URLs in batches with limited threads
    process_urls_in_batches(all_scrape_urls, max_workers=500, batch_size=1000)
            
    print("\nPHASE 2 COMPLETE: Scraped details for all URLs.\n")

    print("PHASE 3: Writing data to CSV...")
    if drama_data_list:
        all_headers = set()
        for d in drama_data_list:
            all_headers.update(d.keys())
        
        output_filename = "mydramalist_dump2.csv"
        with open(output_filename, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(list(all_headers)))
            writer.writeheader()
            writer.writerows(drama_data_list)
        print(f"SUCCESS: Dumped data for {len(drama_data_list)} items to {output_filename}")
    else:
        print("No data was collected to write to file.")

if __name__ == "__main__":
    main()