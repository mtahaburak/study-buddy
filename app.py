"""
app.py
Streamlit frontend for Study Buddy with Interactive Practice Quizzes.
"""

import os
import uuid
from dotenv import load_dotenv
import httpx
import streamlit as st

# Load environment configuration
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Page Configuration
st.set_page_config(
    page_title="Study Buddy",
    page_icon="🎓",
    layout="wide",
)

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "turns" not in st.session_state:
    st.session_state.turns = 0

if "active_quiz" not in st.session_state:
    st.session_state.active_quiz = None

if "quiz_id" not in st.session_state:
    st.session_state.quiz_id = str(uuid.uuid4())[:8]

if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False

# Sidebar
with st.sidebar:
    st.title("🎓 Study Buddy")
    st.caption("Your Step-by-Step AI Tutor")
    st.divider()

    # Subject Selector
    subject = st.selectbox(
        "Choose Subject",
        options=["Math", "Science", "English", "Computer Science"],
        index=0,
    )

    st.markdown(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
    st.markdown(f"**User Turns:** `{st.session_state.turns}`")
    st.divider()

    # New Conversation Button (Requirement 4)
    if st.button("🔄 New Conversation", use_container_width=True):
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(
                    f"{BACKEND_URL}/reset",
                    json={"session_id": st.session_state.session_id},
                )
        except Exception:
            pass  # Reset locally even if backend is unreachable

        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.turns = 0
        st.session_state.active_quiz = None
        st.session_state.quiz_id = str(uuid.uuid4())[:8]
        st.session_state.quiz_submitted = False
        st.rerun()

    # Interactive Quiz Me Button (Bonus)
    if st.button("📝 Quiz Me!", use_container_width=True):
        with st.spinner("Generating 3 practice questions..."):
            try:
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(
                        f"{BACKEND_URL}/quiz",
                        json={
                            "session_id": st.session_state.session_id,
                            "subject": subject.lower(),
                        },
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    questions = data.get("questions", [])
                    if questions:
                        st.session_state.active_quiz = questions
                        st.session_state.quiz_id = str(uuid.uuid4())[:8]
                        st.session_state.quiz_submitted = False
                        st.rerun()
                    else:
                        st.error("Quiz service did not return questions. Please try again.")
                else:
                    detail = resp.json().get("detail", resp.text)
                    st.error(f"Failed to generate quiz: {detail}")
            except httpx.ConnectError:
                st.error("Cannot connect to backend server. Make sure it is running on port 8000.")
            except Exception as e:
                st.error(f"Quiz error: {e}")

# Main Chat Interface
st.title(f"📖 {subject} Study Session")
st.write("Welcome to your interactive study session! Ask any question, and I'll help you break it down step by step.")

# Interactive Quiz Section (when active)
if st.session_state.get("active_quiz"):
    st.subheader("📝 Practice Quiz")
    questions = st.session_state.active_quiz
    quiz_id = st.session_state.quiz_id
    submitted = st.session_state.get("quiz_submitted", False)

    for i, q in enumerate(questions):
        st.markdown(f"**Question {i + 1}:** {q.get('question', '')}")
        choice_key = f"quiz_choice_{quiz_id}_{i}"

        st.radio(
            label=f"Options for question {i + 1}:",
            options=q.get("options", []),
            index=None,
            key=choice_key,
            disabled=submitted,
            label_visibility="collapsed",
        )

        if submitted:
            user_choice = st.session_state.get(choice_key)
            correct_choice = q.get("correct_option", "")
            explanation = q.get("explanation", "")

            if user_choice == correct_choice:
                st.success(f"✅ **Correct!** ({user_choice})")
            else:
                st.error(f"❌ **Incorrect.** You selected: `{user_choice}`. Correct answer: **{correct_choice}**")
            st.info(f"💡 **Explanation:** {explanation}")

        st.write("")

    # Check if all questions have been answered
    all_answered = all(
        st.session_state.get(f"quiz_choice_{quiz_id}_{i}") is not None
        for i in range(len(questions))
    )

    if not submitted:
        if not all_answered:
            st.caption("Please select an answer for all 3 questions to enable Check Answer.")
        if st.button("Check Answer", type="primary", disabled=not all_answered):
            st.session_state.quiz_submitted = True
            st.rerun()
    else:
        # Calculate and display score
        score = sum(
            1
            for i, q in enumerate(questions)
            if st.session_state.get(f"quiz_choice_{quiz_id}_{i}") == q.get("correct_option")
        )
        st.metric(label="Quiz Result", value=f"{score} / {len(questions)}")

        if st.button("Close Quiz"):
            st.session_state.active_quiz = None
            st.session_state.quiz_submitted = False
            st.rerun()

    st.divider()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)

# Chat Input & Response Handling
if user_prompt := st.chat_input("Ask a question or reply to your tutor..."):
    # Render and store user message
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Call FastAPI backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking step by step..."):
            try:
                with httpx.Client(timeout=45.0) as client:
                    response = client.post(
                        f"{BACKEND_URL}/chat",
                        json={
                            "session_id": st.session_state.session_id,
                            "subject": subject.lower(),
                            "message": user_prompt,
                        },
                    )

                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("reply", "")
                    turns = data.get("turns", st.session_state.turns + 1)
                    st.session_state.turns = turns
                    st.markdown(reply, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                else:
                    detail = response.json().get("detail", response.text)
                    st.error(f"Error from Study Buddy backend: {detail}")
            except httpx.ConnectError:
                st.error("Could not connect to the Study Buddy backend. Please ensure the backend server is running on port 8000.")
            except httpx.TimeoutException:
                st.error("The request timed out waiting for the tutor to respond. Please try again.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
