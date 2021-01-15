# -*- coding: utf-8 -*-

import bs4 as bs
import urllib.request
import re
import nltk
import string

from nltk.stem import WordNetLemmatizer, PorterStemmer
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

from unidecode import unidecode
import wikipedia
import requests
import json

import logging

from pprint import pprint, pformat

from flask import Flask, jsonify, request, render_template

logging.basicConfig(filename="log.log", level=logging.DEBUG)
app = Flask(__name__)


def is_url(url):
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

    
def get_wiki_img(wiki_title):
    url = 'https://en.wikipedia.org/w/api.php'
    data = {
        'action': 'query',
        'format' : 'json',
        'formatversion' : 2,
        'prop' : 'pageimages|pageterms',
        'piprop' : 'original',
        'titles' : wiki_title
    }
    response = requests.get(url, data)
    json_data = json.loads(response.text)
    return json_data['query']['pages'][0]['original']['source'] if len(json_data['query']['pages']) >0 else 'Not found'


@app.route("/autosummarise")
def index():
    return render_template("index.html")


@app.route("/autosummarise/summarise", methods=["POST"])
def summary():
    request.get_json()
    article_url = request.form['url']

    # TODO: improve url detection
    if not is_url(article_url):
        wiki_title = wikipedia.search(article_url)
        if len(wiki_title) == 0:
            wiki_title = wikipedia.suggest(article_url)
        else:
            wiki_title = wiki_title[0]
        wiki_page = wikipedia.page(wiki_title, auto_suggest=False)
        article_url = wiki_page.url
        wiki_title = wiki_page.title
        logging.debug(article_url)

        wiki_summary = True
        if wiki_summary:
            logging.debug(wiki_title)
            wiki_img = get_wiki_img(wiki_title)
            summary = "<div style=\"padding: 10px;\">"
            summary += '<h2>' + wiki_title + ' - Wikipedia</h2>'
            summary += '<a href=' + article_url + '>' + article_url + '</a>'
            summary += '<br/><img style="height: 20vh;" src=' + wiki_img + '>'
            summary += '<p>' + \
                wikipedia.summary(wiki_title, sentences=7,
                                  auto_suggest=False) + '</p>'
            summary += "</div>"

            return jsonify(summary)

    scraped_data = urllib.request.urlopen(article_url)
    article = scraped_data.read()

    parsed_article = bs.BeautifulSoup(article, 'lxml')

    paragraphs = parsed_article.find_all('p')

    article_text = ""

    for p in paragraphs:
        article_text += p.text + " \n"

    article_text = re.sub(r'\[[0-9]*\]', ' ', article_text)
    # article_text = unidecode(article_text)
    article_text = re.sub(
        r'[^\w\s' + re.escape(string.punctuation) + ']', ' ', article_text)
    article_text = re.sub(r'\s+', ' ', article_text)
    article_text = re.sub(r'(\w) s ', r"\1's ", article_text)

    formatted_article_text = re.sub('[^a-zA-Z]', ' ', article_text)
    formatted_article_text = re.sub(r'\s+', ' ', formatted_article_text)

    sentence_list = nltk.sent_tokenize(article_text)

    stopwords = nltk.corpus.stopwords.words('english')

    wln = WordNetLemmatizer()

    word_frequencies = {}
    for word in nltk.word_tokenize(formatted_article_text):
        word = wln.lemmatize(word.lower())
        if word not in stopwords:
            if word not in word_frequencies.keys():
                word_frequencies[word] = 1
            else:
                word_frequencies[word] += 1

    maximum_frequency = max(word_frequencies.values())

    for word in word_frequencies.keys():
        word_frequencies[word] = (word_frequencies[word] / maximum_frequency)

    logging.debug(pformat(word_frequencies))

    sentence_scores = {}
    for sent in sentence_list:
        words_tokenised = nltk.word_tokenize(sent.lower())
        logging.debug(sent, words_tokenised, len(words_tokenised), '\n\n')
        for word in words_tokenised:
            if word in word_frequencies.keys():
                if sent not in sentence_scores.keys():
                    sentence_scores[sent] = word_frequencies[word]
                else:
                    sentence_scores[sent] += word_frequencies[word]

        if sent in sentence_scores.keys():
            sentence_scores[sent] /= len(words_tokenised)

    summary_sentences = [k for k, v in sorted(
        sentence_scores.items(), key=lambda item: item[1])][::-1][:7]

    logging.debug('\n\n'.join(summary_sentences))

    summary = "<div style=\"padding: 10px;\">"
    summary += '<h2>' + parsed_article.title.text + '</h2>'
    summary += '<a href=' + article_url + '>' + article_url + '</a>'
    summary += '<p>' + ' '.join(summary_sentences) + '</p>'
    summary += "</div>"

    return jsonify(summary)
