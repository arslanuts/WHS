import os
import streamlit as st
import time
import seaborn as sns
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


def eda(data):
    st.title("Exploratory Data Analysis (EDA)")
    st.write("## Summary Statistics")
    st.write(data.describe())

    st.write("## Data Visualization")
    st.subheader("Histogram for 'postCode'")
    fig = plt.figure()
    plt.hist(data['postCode'], bins=30, color='skyblue')
    st.pyplot(fig)

    st.subheader("Bar plot for 'state'")
    state_counts = data['state'].value_counts()
    st.bar_chart(state_counts)

    st.write("## Data Cleaning")
    st.write("### Missing Values")
    missing_values = data.isnull().sum()
    st.write(missing_values)

    st.write("### Duplicate Rows")
    duplicate_rows = data[data.duplicated()]
    st.write(duplicate_rows)

    st.write("## Outlier Detection")
    st.subheader("Box Plot for 'postCode'")
    plt.figure(figsize=(6, 4))
    sns.boxplot(data['postCode'])
    st.pyplot(plt)

    st.write("## Summary Statistics for 'suburb'")
    st.write(data['suburb'].describe())

    st.subheader("Bar plot for 'suburb'")
    suburb_counts = data['suburb'].value_counts()
    st.bar_chart(suburb_counts)

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
    num_rows_with_reviews = df['review'].notna().sum()

    if num_rows_with_reviews:
        df['review'] = df['review'].astype(str)

        review_lengths = df['review'].str.len()
        st.subheader("Review Length Analysis")
        st.write("Average Review Length:", review_lengths.mean())
        st.write("Maximum Review Length:", review_lengths.max())
        st.write("Minimum Review Length:", review_lengths.min())


def check_misspelled_keywords(keywords):
    spell = SpellChecker()
    misspelled = spell.unknown(keywords)
    suggestions = {keyword: spell.candidates(keyword) for keyword in misspelled}
    return misspelled, suggestions


def nlp(df, keywords):
    st.header("Natural Language Processing Analysis")

    misspelled_keywords, suggestions = check_misspelled_keywords(keywords)
    if misspelled_keywords:
        st.warning("The following keywords may be misspelled:")
        data = []
        for keyword in misspelled_keywords:
            data.append({'Misspelled Keyword': keyword, 'Suggestions': ', '.join(suggestions[keyword])})

        suggestions_table = pd.DataFrame(data)
        st.write(suggestions_table)

    df['cleaned_description'] = df['description'].apply(preprocess_text)
    df['reviews'] = df['review'].apply(preprocess_text)
    descriptions = df['cleaned_description'].dropna()
    reviews = df['reviews'].dropna()

    st.subheader("Descriptions Word Cloud")
    wordcloud = WordCloud(width=800, height=400, background_color="white").generate(" ".join(descriptions))
    st.image(wordcloud.to_array())

    st.subheader("Word Frequency Analysis")
    word_freq = pd.Series(" ".join(descriptions).lower().split()).value_counts()[:20]
    st.bar_chart(word_freq)

    st.subheader("Description Sentiment Analysis")
    sentiments = descriptions.apply(lambda text: TextBlob(text).sentiment.polarity)
    sentiment_labels = ["Positive" if score > 0 else "Negative" if score < 0 else "Neutral" for score in sentiments]
    sentiment_counts = pd.Series(sentiment_labels).value_counts()
    st.bar_chart(sentiment_counts)
    num_rows_with_reviews = scraped_data['review'].notna().sum()

    print(num_rows_with_reviews)
    if num_rows_with_reviews:
        st.subheader("Review Word Cloud")
        review_wordcloud = WordCloud(width=800, height=400, background_color="white").generate(" ".join(reviews))
        st.image(review_wordcloud.to_array())

        st.title("Review Sentiment Analysis")
        st.subheader("Sentiment Analysis")
        sentiments = reviews.apply(lambda text: TextBlob(text).sentiment.polarity)
        sentiment_labels = ["Positive" if score > 0 else "Negative" if score < 0 else "Neutral" for score in sentiments]
        sentiment_counts = pd.Series(sentiment_labels).value_counts()
        st.bar_chart(sentiment_counts)


st.title("Business lookup Tool")
scraped_data = []

st.sidebar.header("Enter Keywords")
keywords = st.sidebar.text_area("Enter keywords separated by commas (e.g., keyword1, keyword2)", height=100)
keywords = [kw.strip() for kw in keywords.split(',')]
st.sidebar.header("Data Filters")
postcode_filter = st.sidebar.text_input("Enter Postcode (optional):")
number_of_records = st.sidebar.text_input("Enter Records (optional):")
if st.sidebar.button("Start"):
    if not keywords:
        st.warning("Please enter at least one keyword.")
    else:
        if scraper_thread and scraped_data.isRunning():
            scraper_thread.terminate()
            scraper_thread = None

        st.info(f"Scraping data for keywords: {', '.join(keywords)}")
        with st.spinner("Scraping data please wait"):
            csv_files = [f for f in os.listdir("data") if f.endswith(".csv")]
            sorted_csv_files = sorted(csv_files, key=lambda x: Path(data_dir, x).stat().st_ctime, reverse=True)
            if csv_files:
                first_csv_file = sorted_csv_files[0]
            else:
                scraper = Scraper([keywords[0]])
                scraper.start()
                while True:
                    csv_files = [f for f in os.listdir("data") if f.endswith(".csv")]
                    sorted_csv_files = sorted(csv_files, key=lambda x: Path(data_dir, x).stat().st_ctime, reverse=True)
                    if csv_files:
                        first_csv_file = sorted_csv_files[0]
                        break
                    time.sleep(1)
        try:
            scraped_data = pd.read_csv(f"data/{first_csv_file}")
            df = pd.DataFrame(scraped_data)
            if postcode_filter:
                df = df[df['postCode'] == int(postcode_filter)]

            if number_of_records:
                df = df.head(int(number_of_records))
            df['email_domain'] = df['email'].apply(extract_email_domain)
            df['sentiment'] = df['review'].apply(perform_sentiment_analysis)
            st.write(df)
            eda(df)
            nlp(df,keywords)
        except Exception as e:
            print(e)
            st.warning("Something went wrong")


