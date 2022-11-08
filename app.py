import streamlit as st
import pandas as pd
import pickle
from bs4 import BeautifulSoup
import requests
import math
import re
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import operator

st.title('Swoonflix')

@st.cache
def get_data():
	path = r'thisIsLast.csv'
	f=pd.read_csv(path,encoding='utf-8-sig')
	return f
def set_data(f,c1,c2):
	f=f.loc[((f["category"] == str(c1)) & (f["country"] == str(c2)))]
	f=f.reset_index(drop=True)
	return f

temp=get_data()

category_name = st.selectbox('What are you looking for?', temp['category'].unique())
country_name= st.selectbox('Select a country', temp['country'].unique())

df = temp.loc[((temp["category"] == category_name) & (temp["country"] == country_name))]
df.fillna('Info not available',inplace=True)
selected_dramas = st.selectbox(
     'Search for any movie or a show that you like',
     df['Name'])
#creating df copy
dramas=df[['Name', 'category', 'country', 'num_episodes', 'aired',
       'orginal_network', 'duration', 'watchers', 'director', 'screenwriter',
       'rating', 'num_raters', 'cast_names', 'genre_names', 'tag_names',
       'synopsis', 'url']]
dramas['tag_names'] =dramas['tag_names'].str.replace(" ","")
dramas['cast_names'] =dramas['cast_names'].str.replace(" ","")
dramas['genre_names'] =dramas['genre_names'].str.replace(" ","")

#cosine logic
WORD = re.compile(r"\w+")
def get_cosine(vec1, vec2):
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([vec1[x] ** 2 for x in list(vec1.keys())])
    sum2 = sum([vec2[x] ** 2 for x in list(vec2.keys())])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    else:
        return float(numerator) / denominator
def text_to_vector(text):
    words = WORD.findall(text)
    return Counter(words)


option = st.selectbox(
     'Choose recommedations based on category:',
     ('Genre','Cast'))

top = st.slider('Swoon into our top N recommendations', 0, 100, 10)
st.write("Suggesting", top,"best ",category_name," based on ",option," :)")

def recommend(n,t=top,based=option):
	idx =dramas[dramas['Name'] == n].index[0]
	if based=='Genre':
		dramas['comb'] = dramas['genre_names']+dramas['tag_names']
		dramas['comb']=dramas['comb'].str.lower()
		vector1=dramas['genre_names'].loc[idx]+dramas['tag_names'].loc[idx]
	if based=='Cast':
		dramas['comb'] =dramas['cast_names']
		dramas['comb']=dramas['comb'].str.lower()
		vector1=dramas['cast_names'].loc[idx]
	vector1=vector1.lower()
	my_dict = []
	for i,j in enumerate(dramas.comb):
		try:
			my_dict.append(get_cosine(text_to_vector(vector1),text_to_vector(j)))
		except:
			my_dict.append(get_cosine(text_to_vector(str(vector1)),text_to_vector(str(j))))
	enumerate_object = enumerate(my_dict)
	distances = sorted(enumerate_object,reverse=True, key=operator.itemgetter(1))
	recommended_names = []
	recommended_posters = []
	recommended_rating=[]
	recommended_episodes=[]
	recommended_network=[]
	recommended_aired=[]
	recommended_genre=[]
	recommended_director=[]
	recommended_cast=[]
	recommended_synopsis=[]
	for i in distances[1:t+1]:
		recommended_posters.append(df.iloc[i[0]].url)
		recommended_names.append(df.iloc[i[0]].Name)
		recommended_rating.append(df.iloc[i[0]].rating)
		recommended_episodes.append(df.iloc[i[0]].num_episodes)
		recommended_network.append(df.iloc[i[0]].orginal_network)
		recommended_aired.append(df.iloc[i[0]].aired)
		recommended_genre.append(df.iloc[i[0]].genre_names)
		recommended_director.append(df.iloc[i[0]].director)
		recommended_cast.append(df.iloc[i[0]].cast_names)
		recommended_synopsis.append(df.iloc[i[0]].synopsis)
	return recommended_names,recommended_posters,recommended_rating,recommended_aired,recommended_episodes,recommended_network,recommended_director,recommended_cast,recommended_synopsis,recommended_genre


if st.button('Recommend'):
	recommended_names,recommended_posters,recommended_rating,recommended_aired,recommended_episodes,recommended_network,recommended_director,recommended_cast,recommended_synopsis,recommended_genre = recommend(selected_dramas,top)
	for i in range(0,top):
		with st.container():
			if category_name=='Drama':
				st.subheader(recommended_names[i])
				st.image(recommended_posters[i])
				st.markdown('###### Rating:')
				st.text(recommended_rating[i])
				st.markdown('###### Aired on:')
				st.text(recommended_aired[i])
				st.markdown('###### Episodes:')
				st.text(recommended_episodes[i])
				st.markdown('###### Network:')
				st.text(recommended_network[i])
				st.markdown('###### Genre:')
				st.text(recommended_genre[i])
				st.markdown('###### Director:')
				st.text(recommended_director[i])
				st.markdown('###### Cast:')
				st.text(recommended_cast[i])
				st.markdown('###### Synopsis:')
				st.caption(recommended_synopsis[i])
				st.text("")
				st.text("")
			else:
				st.subheader(recommended_names[i])
				st.image(recommended_posters[i])
				st.markdown('###### Rating:')
				st.text(recommended_rating[i])
				st.markdown('###### Aired on:')
				st.text(recommended_aired[i])
				st.markdown('###### Genre:')
				st.text(recommended_genre[i])
				st.markdown('###### Director:')
				st.text(recommended_director[i])
				st.markdown('###### Cast:')
				st.text(recommended_cast[i])
				st.markdown('###### Synopsis:')
				st.caption(recommended_synopsis[i])
				st.text("")
				st.text("")
