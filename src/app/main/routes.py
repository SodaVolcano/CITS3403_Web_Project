""" Route and view function definitions for the main blueprint """

from flask import render_template, redirect, url_for, flash, request, session, jsonify
from werkzeug.urls import url_parse

from flask_wtf import FlaskForm
from flask_login import login_user, logout_user, current_user, login_required
from flask_session import Session

from . import main
from .forms import LoginForm, RegisterForm
from .models import Users, Messages, Conversations, Robot
from .chatbot import ChatbotAgent, ChatbotMediator
import json

import json
import random

from app import db


@main.route("/", methods=["GET", "POST"])
@main.route("/index", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@main.route("/about")
def about():
    return render_template("about_us.html")


@main.route("/chat", methods=["GET"])
@login_required
def chat():
    print("Arrived at chat")
    return render_template("chat.html")


@main.route("/replace_conversation", methods=["GET"])
def replace_conversation():
    conversation_id = request.args.get("new_id").strip('"')
    print("Replacing with conversation: " + str(conversation_id))
    print("Getting conversation from db")

    query = Messages.query.filter_by(conversation_ID=(conversation_id)).all()
    session["conversation_id"] = conversation_id
    session["chatbot"] = ChatbotAgent("chatgpt")

    print(query)

    messages = []
    print("listing msgs from db")
    for result in query:
        print(result.body)
        msg = {
            "id": result.id,
            "content": result.body,
            "conversationID": result.conversation_ID,
            "speaker": result.speaker,
            "emotion": result.emotion,
            "timestamp": result.timestamp,
        }
        messages.append(msg)
    return jsonify(
        {"status": "OK", "conversation_id": conversation_id, "conversation": messages}
    )


@main.route("/get_conversations", methods=["GET"])
def get_conversations():
    # get conversations and check if empty
    print("Getting conversations for user: " + str(current_user.id))  # type: ignore
    get_conversation = Conversations.query.filter_by(user_id=current_user.id).all()  # type: ignore
    if get_conversation is None:
        print("No conversations!")
        return jsonify({"status": "EMPTY", "conversations": None})
    sorted_conversations = sorted(get_conversation, key=lambda x: x.timestamp)

    # convert to json object
    my_conversations = []
    for conversation in sorted_conversations:
        print(conversation.id)
        my_conversations.append(str(conversation.id))
    # return a list of all conversations
    return jsonify({"status": "OK", "conversations": my_conversations})


@main.route("/process-msg", methods=["POST"])
def process_msg():
    messages = request.form.get("messages")
    conversation_id = request.form.get("conversation_id")

    if messages is None:
        return jsonify({"status": "ERROR", "message": "No message provided"}), 400
    if "chatbot" not in session:
        return jsonify({"status": "ERROR", "message": "Chatbot not initialized"}), 400

    query_messages = Messages.query.filter_by(conversation_ID=(conversation_id)).all()
    history = []
    for msg in query_messages:
        history.append({"role": "user", "content": msg.body})
    messages = json.loads(messages)

    for msg in messages:
        Messages.add_msg(msg, "happy", "user", session["conversation_id"])

    reply = ChatbotMediator.prompt_chatbot(messages, history, session["chatbot"])

    for msg in reply:
        Messages.add_msg(msg, "happy", "robot", session["conversation_id"])

    return jsonify(
        {
            "status": "OK",
            "messages": reply,
            "conversation_id": session["conversation_id"],
        }
    )


@main.route("/init_conversation", methods=["POST"])
def init_conversation():
    """Initialize the conversation agent when user starts new session"""
    try:
        conversationID = 0
        while Conversations.conversation_exists(conversationID):
            conversationID = random.randint(0, 10000)

        session["conversation_id"] = conversationID

        # Add conversation to db

        Conversations.add_conversation(
            conversationID, current_user.id, session["chatbot"].id
        )

        return jsonify(
            {
                "status": "OK",
                "conversation_id": str(session["conversation_id"]),
                "error": "none",
            }
        )
    except KeyError:
        return jsonify(
            {
                "status": "FAILED",
                "conversation_id": -1,
                "error": "Chatbot not initialiazed",
            }
        )


@main.route("/init_chatbot", methods=["POST"])
def init_chatbot():
    """Initialize the chatbot agent when user starts new session"""
    session["chatbot"] = ChatbotAgent("chatgpt")
    chatbot_id = session["chatbot"].id

    # add new robot
    Robot.add_robot("rob", "", chatbot_id)

    return jsonify({"status": "OK", "bot_id": session["chatbot"].id})


# To logout user
@main.route("/signup", methods=["GET", "POST"])
def signup():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        # Generate New User

        # Add user to database
        Users.add_user(
            register_form.username.data,
            register_form.email.data,
            register_form.password.data,
        )

        # Send to login page
        return redirect(url_for(".login"))
    return render_template("signup.html", form=register_form)


# To logout user
@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(".index"))
    login_form = LoginForm()
    if login_form.validate_on_submit():
        # Get User from table
        user = Users.query.filter_by(username=login_form.username.data).first()

        # Check for invalid details
        if user is None or not user.check_password(login_form.password.data):
            return redirect(url_for(".login"))

        # login user
        login_user(user, remember=login_form.remember_me.data)

        # redirect to previous page if necessary
        next_page = request.args.get("next")
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for(".index")
        return redirect(next_page)

    return render_template("login.html", form=login_form)


# To logout user
@main.route("/logout")
def logout():
    # logout user
    logout_user()
    return redirect(url_for(".index"))
