import base64
import os
import streamlit as st
import time
import seaborn as sns
from PyQt5.QtWebEngineWidgets import QWebEngineView
from wordcloud import WordCloud
from textblob import TextBlob
import pandas as pd
import matplotlib.pyplot as plt
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string
from YellowPagesScraper import Scraper
import numpy as np
from spellchecker import SpellChecker
from nltk.corpus import wordnet
import nltk

nltk.download("wordnet")
from pathlib import Path

scraper_thread = None
data_dir = "data"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)


def perform_sentiment_analysis(text):
    if isinstance(text, str):
        analysis = TextBlob(text)
        return analysis.sentiment.polarity
    return np.nan


def extract_email_domain(email):
    if pd.notna(email):
        parts = email.split('@')
        if len(parts) == 2:
            return parts[1]
    return None


def preprocess_text(text):
    if not pd.isna(text):
        tokens = word_tokenize(text.lower())
        tokens = [word for word in tokens if word not in string.punctuation]
        tokens = [word for word in tokens if word not in stopwords.words('english')]
        return " ".join(tokens)
    else:
        return ""


def get_related_keywords(keywords, top_n=5):
    related_keywords_dict = {}
    list_of_keywords = set()
    for keyword in keywords:
        synonyms = set()
        list_of_keywords.add(keyword)
        for syn in wordnet.synsets(keyword):
            for lemma in syn.lemmas():
                synonym = lemma.name()
                if synonym.lower() not in list_of_keywords:
                    synonyms.add(synonym)
        synonyms.add(keyword)
        related_keywords_dict[keyword] = list(synonyms)[:top_n]
        list_of_keywords.update(synonyms)
    list_of_keywords = list(list_of_keywords)
    print(list_of_keywords)
    print(related_keywords_dict)
    return related_keywords_dict, list_of_keywords


def eda(data):
    st.title("Exploratory Data Analysis (EDA)")
    st.write("## Summary Statistics")
    st.write(data.describe())

    st.write("## Data Visualization")
    st.subheader("Histogram for 'postCode'")
    fig = plt.figure()
    plt.hist(data['postCode'], bins=30, color='skyblue')
    st.pyplot(fig)

    st.write("## Geospatial Analysis")
    st.subheader("Map of Locations")
    locations = data[['latitude', 'longitude']]
    st.map(locations)

    st.header("Email Domains EDA")
    st.subheader("Unique Email Domains")
    unique_domains = df['email_domain'].unique()
    st.write(unique_domains)

    st.subheader("Email Domain Counts")
    domain_counts = df['email_domain'].value_counts()
    st.bar_chart(domain_counts)


def check_misspelled_keywords(keywords):
    spell = SpellChecker()
    misspelled = spell.unknown(keywords)
    suggestions = {keyword: spell.candidates(keyword) for keyword in misspelled}
    return misspelled, suggestions


def nlp(df, keywords):
    st.header("Natural Language Processing Analysis")
    misspelled_keywords, suggestions = check_misspelled_keywords(keywords)
    if misspelled_keywords:
        data = []
        for keyword in misspelled_keywords:
            suggestions_list = suggestions.get(keyword, [])
            if suggestions_list:
                data.append({'Misspelled Keyword': keyword, 'Suggestions': ', '.join(suggestions_list)})
        if data:
            st.warning("The following keywords may be misspelled:")
            suggestions_table = pd.DataFrame(data)
            st.write(suggestions_table)

    df['cleaned_description'] = df['description'].apply(preprocess_text)
    df['reviews'] = df['review'].apply(preprocess_text)
    descriptions = df['cleaned_description'].dropna()

    st.subheader("Descriptions Word Cloud")
    wordcloud = WordCloud(width=800, height=400, background_color="white").generate(" ".join(descriptions))
    st.image(wordcloud.to_array())


def create_dataframe_download_link(dataframe, filename):
    csv = dataframe.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Click to download {filename}</a>'


st.title("Business lookup Tool")
scraped_data = []

st.sidebar.header("Enter Keywords")
keywords = st.sidebar.text_area("Enter keywords separated by commas (e.g., keyword1, keyword2)", height=100)
key_list = keywords.split(',')
keywords = []
for key in key_list:
    kw = key.strip()
    if kw:
        keywords.append(kw)
st.sidebar.header("Data Filters")
postcode_filter = st.sidebar.text_input("Enter Postcode (optional):")
number_of_records = st.sidebar.text_input("Enter Records (optional):")
new_scrape = st.sidebar.checkbox("New Scrape")
if st.sidebar.button("Start"):
    csv_files = [f for f in os.listdir("data") if f.endswith(".csv")]
    print(csv_files)
    if (not keywords and new_scrape) or (not keywords and not csv_files):
        st.warning("Please enter at least one keyword.")
    else:
        scraper = None
        if new_scrape:
            for filename in os.listdir(data_dir):
                if filename.endswith(".csv"):
                    file_path = os.path.join(data_dir, filename)
                    os.remove(file_path)

        if keywords:
            keywords_data, keywords = get_related_keywords(keywords)
            related_df = pd.DataFrame(keywords_data)
            st.write(related_df)
            st.markdown(create_dataframe_download_link(related_df, "related_keywords.csv"), unsafe_allow_html=True)
            st.info(f"Scraping data for keywords: {', '.join(keywords)}")
        with st.spinner("Scraping data please wait"):
            if new_scrape or not csv_files:
                scraper = Scraper(keywords)
                scraper_thread = scraper
                scraper.start()
            while True:
                csv_files = [f for f in os.listdir("data") if f.endswith(".csv")]
                sorted_csv_files = sorted(csv_files, key=lambda x: Path(data_dir, x).stat().st_ctime, reverse=True)
                if csv_files:
                    first_csv_file = sorted_csv_files[0]
                    if scraper and scraper.isRunning():
                        scraper.quit()
                        scraper.terminate()
                    break
                time.sleep(1)

        try:
            scraped_data = pd.read_csv(f"data/{first_csv_file}")
            df = pd.DataFrame(scraped_data)
            df = df[['name', 'abn'] + [col for col in df.columns if col not in ['name', 'abn']]]
            if postcode_filter:
                df = df[df['postCode'] == int(postcode_filter)]

            if number_of_records:
                df = df.head(int(number_of_records))
            df['email_domain'] = df['email'].apply(extract_email_domain)
            df['sentiment'] = df['review'].apply(perform_sentiment_analysis)
            st.write(df)
            st.markdown(create_dataframe_download_link(df, "scraped_data.csv"), unsafe_allow_html=True)
            eda(df)
            nlp(df, keywords)
        except Exception as ex:
            print(ex)
            st.warning(f"Something went wrong getting error: {ex}")
