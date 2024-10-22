import os
import random
import numpy as np
import pickle
import json
from flask import Flask, render_template, request, session
from flask_ngrok import run_with_ngrok
import nltk
from tensorflow.keras.models import load_model
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import sent_tokenize
from transformers import pipeline

lemmatizer = WordNetLemmatizer()
nltk.download('punkt')

# Définir le répertoire de base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# initialisation du chat
model = load_model(os.path.join(BASE_DIR, "chatbot_model.keras"))
data_file = open(os.path.join(BASE_DIR, "intents.json")).read()
words = pickle.load(open(os.path.join(BASE_DIR, "words.pkl"), "rb"))
classes = pickle.load(open(os.path.join(BASE_DIR, "classes.pkl"), "rb"))

# Initialisation du modèle de langage avancé
nlp = pipeline("text-generation", model="dbddv01/gpt2-french-small")

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Clé secrète pour les sessions
# run_with_ngrok(app)

# Mémoire de la conversation
conversation_memory = []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get", methods=["POST"])
def chatbot_response():
    msg = request.form["msg"]

    # Charger et traiter le fichier JSON des intentions
    data_file = open(os.path.join(BASE_DIR, "intents.json")).read()
    intents = json.loads(data_file)

    # Segmenter le message en phrases distinctes
    sentences = sent_tokenize(msg)
    responses = []

    for sentence in sentences:
        if sentence.lower().startswith("je m'appelle"):
            name = sentence[13:].strip()
            ints = predict_class(sentence, model)
            res = getResponse(ints, intents, name)
        elif sentence.lower().startswith("bonjour, je m'appelle"):
            name = sentence[20:].strip()
            ints = predict_class(sentence, model)
            res = getResponse(ints, intents, name)
        else:
            ints = predict_class(sentence, model)
            if not ints:
                res = get_noanswer_response(intents)
            else:
                res = getResponse(ints, intents)
        
        # Adapter et contextualiser la réponse avec GPT-2
        res = generate_contextual_response(res, msg)
        responses.append(res)

    # Mettre à jour la mémoire de la conversation
    conversation_memory.append({"user": msg, "bot": responses})

    # Combiner les réponses pour chaque phrase en une seule réponse
    final_response = " ".join(responses)
    return final_response

def get_noanswer_response(intents_json):
    for intent in intents_json["intents"]:
        if intent["tag"] == "noanswer":
            return random.choice(intent["responses"])
    return "Désolé, je ne vous ai pas compris."

# fonctionnalités du chat
def clean_up_sentence(sentence):
    sentence_words = nltk.word_tokenize(sentence)
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]
    return sentence_words

# retourner le sac de mots sous forme de tableau : 0 ou 1 pour chaque mot dans le sac qui existe dans la phrase
def bow(sentence, words, show_details=True):
    # tokeniser le modèle
    sentence_words = clean_up_sentence(sentence)
    # sac de mots - matrice de N mots, matrice de vocabulaire
    bag = [0] * len(words)
    for s in sentence_words:
        for i, w in enumerate(words):
            if w == s:
                # assigner 1 si le mot actuel est dans la position du vocabulaire
                bag[i] = 1
                if show_details:
                    print("trouvé dans le sac : %s" % w)
    return np.array(bag)

def predict_class(sentence, model):
    # filtrer les prédictions en dessous d'un seuil
    p = bow(sentence, words, show_details=False)
    res = model.predict(np.array([p]))[0]
    ERROR_THRESHOLD = 0.25
    results = [[i, r] for i, r in enumerate(res) if r > ERROR_THRESHOLD]
    # trier par force de probabilité
    results.sort(key=lambda x: x[1], reverse=True)
    return_list = []
    for r in results:
        return_list.append({"intent": classes[r[0]], "probability": str(r[1])})
    return return_list

def getResponse(ints, intents_json, name=None):
    if not ints:
        return get_noanswer_response(intents_json)
    tag = ints[0]["intent"]
    list_of_intents = intents_json["intents"]
    for i in list_of_intents:
        if i["tag"] == tag:
            result = random.choice(i["responses"])
            if name:
                result = result.replace("{n}", name)
            break
    return result

# Fonction pour générer des réponses contextuelles avec un modèle de langage avancé
def generate_contextual_response(response, user_input):
    context = " ".join([f"User: {entry['user']} Bot: {entry['bot']}" for entry in conversation_memory])
    prompt = f"{context} User: {user_input} Bot: {response}"
    conversation = nlp(prompt, max_new_tokens=50, num_return_sequences=1, pad_token_id=50256, truncation=True)
    generated_text = conversation[0]['generated_text']

    # Nettoyer la réponse générée pour supprimer les préfixes "User:" et "Bot:"
    generated_text = generated_text.replace("User:", "").replace("Bot:", "").strip()

    return generated_text

if __name__ == "__main__":
    app.run()