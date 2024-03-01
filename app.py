#!/usr/bin/python3.9
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import csv
import pandas as pd
import psycopg2
import os
import random
import string
from psycopg2.extras import Json
import os
import json
import io
import math

app = Flask(__name__)
app.config['static_url_path'] = 'static'

ANCHOR_FILE_PATH = "data/example_anchor_answer_info.csv"
ESSAY_PATH  = "articles/0001.txt"

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI') # set your database url at system or replace this string with your database url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#subquestions
subquestions = [
        {
            'id': 1,
            'text': 'Is this question make sense?',
            'options': ['1. Yes', '2. No']
        },
        {
            'id': 2,
            'text': 'Does the “answer sentence” actually answer this question?',
            'options': ['1. Explicit and direct answer',
             '2. Unfocused answer',
             '3. Not-an-answer']
        },
        {
            'id': 3,
            'text': 'Does the question contain new concepts that a reader would be hard to come up with? (By “new concepts”, we mean concepts that cannot be easily inferred by world knowledge from existing ones).',
            'options': ['1. This question does not contain new concepts.',
             '2. Answer leakage',
             '3. Hallucination']
        },
        {
            'id': 4,
            'text': 'Is this question grounded well in the anchor sentence?',
            'options': ['1. The question is fully grounded in the anchor sentence',
             '2. Some parts of the question is grounded in the anchor sentence',
             '3. The question is not at all grounded in the anchor sentence']
        },
        {
            'id': 5,
            'text': 'You may notice other issues with the questions and if so please indicate below. Examples of these issues include:',
            'options': ['1. Redundant question: question already answered in anchor',
             '2. Question too generic to be informative/can be asked anywhere in the document',
             '3. Anything else?']
        }
    ]

file_list = ["0001"]

def retrieve_article_by_id(data_df, article_id):
  for i in range(len(data_df)):
    if(data_df.iloc[i][0][0]['ArticleID'] == article_id):
      return data_df.iloc[i][0][0]

def read_sampling_index(df):
    sample_file_path = "data/example_sampling.csv"
    sampled_df = pd.read_csv(sample_file_path)
    sampled_indices = list(sampled_df['selected_row_number'] - 1)
    sampled_df = df.loc[sampled_indices].sort_index()

    return sampled_df

def read_question(anchor_info_path):
    df = pd.read_csv(anchor_info_path) 
    df = df.reset_index()
    df = df.rename(columns={df.columns[0]: "index"})

    df = read_sampling_index(df)
    
    questions = []
    for index, row in df.iterrows():
        # Extract the values from the row
        question_id = index
        question_text = row['questions'].replace('<|endoftext|>', '')
        anchor_id = int(row["anchor_id"])
        answer_id = row["answer_id"]
        sentences = [anchor_id, answer_id]

        question = {
            'id': question_id,
            'text': question_text,
            'subquestions': subquestions,
            'sentences': sentences
        }
        questions.append(question)
    return questions

def read_context(essay_path):
    with open(essay_path, 'r') as f:
        essay_lines = f.readlines()
    essay_context = {i+1: line.strip() for i, line in enumerate(essay_lines)}
    return essay_context

def read_instructions():
    with open('instructions.txt', 'r') as file:
        instructions = file.readlines()
    return instructions
    
class annotation(db.Model):
    __tablename__ = 'long_annotation'

    sampleid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    essay_id = db.Column(db.String(10), nullable=False)
    survey_code = db.Column(db.String(10), nullable=False)
    answer_dict = db.Column(db.String(5000))
    annotator = db.Column(db.String(100))

    def __init__(self, essay_id, survey_code, answer_dict=None, annotator=None):
        self.essay_id = essay_id
        self.survey_code = survey_code
        self.answer_dict = answer_dict
        self.annotator = annotator

    def __repr__(self):
        return self.survey_code

@app.route("/next", methods=['GET', 'POST'])
def next():
    current_url = request.referrer
    next_num = (int(current_url.split("=")[-1])+1)%len(file_list)
    return redirect("/id="+str(next_num))

@app.route("/previous", methods=['GET', 'POST'])
def previous():
    current_url = request.referrer
    next_num = (int(current_url.split("=")[-1])-1)%len(file_list)
    return redirect("/id="+str(next_num))

@app.route("/id=<uniqueid>")
def start(uniqueid):
    questions = read_question(ANCHOR_FILE_PATH)
    essay_context = read_context(ESSAY_PATH)
    instructions = read_instructions()
    return render_template('index.html', essay_context=essay_context, questions=questions, instructions=instructions, article_number="0001")

@app.route('/')
def index():
    return redirect('/id=0')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

@app.route('/load_result', methods=['GET', 'POST'])
def load_result():
    default_csv_file = "result/result.csv"

    if request.method == 'POST':
        if 'survey_code' not in request.form:
            flash('No survey code provided')
            return render_template('load_result.html', survey_code="", answer_dict={})

        survey_code = request.form['survey_code']
        file = request.files.get('file')

        if file and file.filename != '':
            try:
                answer_df = pd.read_csv(io.StringIO(file.read().decode('utf-8')))
            except Exception as e:
                flash(f'Error processing the file: {str(e)}')
                return render_template('load_result.html', survey_code=survey_code, answer_dict={})
        else:
            answer_df = pd.read_csv(default_csv_file)

        if survey_code not in answer_df['survey_code'].values:
            flash('Survey code not found in the CSV file')
            return render_template('load_result.html', survey_code=survey_code, answer_dict={})

        answer_str = answer_df.loc[answer_df['survey_code'] == survey_code, 'answer_dict'].iloc[0]
        if isinstance(answer_str, str):
            answer_str = answer_str.replace('null', 'None')
            answer_str = answer_str.replace('false', 'False')
            answer_str = answer_str.replace('true', 'True')
            answer_dict = eval(answer_str)
        elif answer_str is None or math.isnan(answer_str):
            # Handle the case where answer_str is None or NaN
            answer_dict = {}
        return render_template('load_result.html', survey_code=survey_code, answer_dict=answer_dict)

    return render_template('load_result.html', survey_code="", answer_dict={})


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    answers = {}
    subquestion_ids = [1,2,3,4,5]
    current_url = request.referrer
    current_data_idx = int(current_url.split("=")[-1])
    essay_id = file_list[current_data_idx]
    survey_code = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    annotator = 'turker'
    questions = read_question(ANCHOR_FILE_PATH)
    for question in questions:
        question_id = question['id']
        subquestions = question['subquestions']
        sub_answers = {}

        textbox_input = request.form[f'question{question_id}-extra-info']
        multiQ_checked = request.form.get(f'question{question_id}-multiQ-checked', False) == "on"
        
        #check if question first criteria not answered
        if(request.form.get('question%s-subquestion1'%(question_id)) is None):
            survey_code = "Your answers are not compelete, please go back check."
            return render_template('feedback.html', survey_code=survey_code, answer_dict={})
        #check if question is bad, if so skip following annotation
        if (request.form.get('question%s-subquestion1'%(question_id)).split(".")[0] == "2"):
            sub_answers['subQ-1:'] = "No"
            sub_answers['subQ-2:'] = "skipped"
            sub_answers['subQ-3:'] = "skipped"
            sub_answers['subQ-4:'] = "skipped"
            sub_answers['subQ-5:'] = "skipped"
            sub_answers['extra-info'] = textbox_input
            sub_answers['multiQ_checked'] = multiQ_checked
            answers["Q-%d:" %(question_id)] = sub_answers
            continue
        for subquestion_id in subquestion_ids[:-1]:
            if(request.form.get('question%s-subquestion%d'%(question_id, subquestion_id)) is not None):
                answer = request.form.get('question%s-subquestion%d'%(question_id, subquestion_id))
                selected_option_number = answer.split(".")[0]
                sub_answers['subQ-%d:'%(subquestion_id)] = selected_option_number
            else:
                #some question is not complete
                entry = annotation(essay_id = essay_id, survey_code=survey_code, annotator=annotator)
                db.session.add(entry)
                db.session.commit()
                survey_code = "Your answers are not compelete, please go back check."
                return render_template('feedback.html', survey_code=survey_code, answer_dict={})
        if(request.form.get('question%s-subquestion5'%(question_id)) is not None):
            sub_answers['subQ-5:'] = request.form.get('question%s-subquestion5'%(question_id)).split(".")[0]
        else:
            sub_answers['subQ-5:'] = None
        sub_answers['extra-info'] = textbox_input
        sub_answers['multiQ_checked'] = multiQ_checked
        answers["Q-%d:" %(question_id)] = sub_answers
    d = {}
    print(answers)
    d['essay_id'] = essay_id
    d['survey_code'] = survey_code
    d['annotator'] = annotator
    d["answer_dict"] = Json(answers)
    entry = annotation(**d)
    db.session.add(entry)
    db.session.commit()
    return render_template('feedback.html', survey_code=survey_code, answer_dict=answers)

@app.route('/override_answer', methods=['POST'])
def override_answer():
    default_csv_file = "result/result.csv"
    answer_df = pd.read_csv(default_csv_file)

    # Get the input values from the form
    override_question = request.form['override_question']
    override_criteria = request.form['override_criteria']
    override_result = request.form['override_result']
    survey_code = request.form['survey_code']

    answer_str = answer_df.loc[answer_df['survey_code'] == survey_code, 'answer_dict'].iloc[0]

    if isinstance(answer_str, str):
        answer_str = answer_str.replace('null', 'None')
        answer_str = answer_str.replace('false', 'False')
        answer_str = answer_str.replace('true', 'True')
        answer_dict = eval(answer_str)


    print("Original answer_dict:", answer_dict)
    answer_dict_copy = answer_dict.copy()
    print("answer_dict_copy:", answer_dict_copy)

    answer_dict_copy.setdefault(f"Q-{override_question}:", {})
    answer_dict_copy[f"Q-{override_question}:"][f"subQ-{override_criteria}:"] = override_result
    print("Updated answer_dict_copy:", answer_dict_copy)

    # Convert the answer_dict_copy back to a string
    answer_str_copy = json.dumps(answer_dict_copy)

    print("Before updating DataFrame:")
    print(answer_df)

    # Use the index with the .loc[] accessor for assignment
    index = answer_df.loc[answer_df['survey_code'] == survey_code].index[0]
    answer_df.loc[index, 'answer_dict'] = answer_str_copy
    answer_df.to_csv(default_csv_file)

    print("After updating DataFrame:")
    print(answer_df)

    return render_template('load_result.html', survey_code=survey_code, answer_dict=answer_dict_copy)

if __name__ == '__main__':
    app.run(debug=True)