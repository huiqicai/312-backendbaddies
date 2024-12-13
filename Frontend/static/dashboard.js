let socket = null;

function initWs() {
    const socketProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socketUrl = `${socketProtocol}://${window.location.host}`;

    socket = io(socketUrl, {
        transports: ['websocket'], 
        upgrade: false, 
    });

    socket.on('connect', () => {
        console.log("WebSocket connection established");
        joinQuizRooms(); 
    });

    socket.on('new_comment', (data) => {
        const commentsList = document.querySelector(`#quiz-${data.quiz_id} .comments-list`);
        if (commentsList) {
            const commentHtml = `<li><strong>${data.username}</strong>: ${data.text}</li>`;
            commentsList.insertAdjacentHTML('beforeend', commentHtml);
        }
    });

    socket.on('like_quiz', (data) => {
        const likeCountElement = document.querySelector(`#like-count-${data.quiz_id}`);
        if (likeCountElement) {
            likeCountElement.textContent = data.likes_users.length;
        }
    });

    socket.on('update_likes', (data) => {
        const { quiz_id, likes_count, likes_users } = data;

        const likeCountElement = document.querySelector(`#like-count-${quiz_id}`);
        if (likeCountElement) {
            likeCountElement.textContent = likes_count;
        }

        const likesList = document.getElementById(`likes-list-${quiz_id}`);
        if (likesList) {
            likesList.innerHTML = ""; 
            likes_users.forEach((user) => {
                const listItem = document.createElement("li");
                listItem.textContent = user;
                likesList.appendChild(listItem);
            });
        }
    });

    socket.on('disconnect', () => {
        console.log("WebSocket connection closed");
    });

    socket.on('error', (error) => {
        console.error("WebSocket error:", error);
    });

    const timerElement = document.getElementById('timer');

    socket.on("update_timer", (data) => {
        const timeLeft = data.time_left;

        if (timeLeft >= 0) {
            const hours = Math.floor(timeLeft / 3600);
            const minutes = Math.floor((timeLeft % 3600) / 60);
            const seconds = timeLeft % 60;

            timerElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        } else {
            timerElement.textContent = "00:00:00";
        }
    });

}
function joinQuizRooms() {
    const quizItems = document.querySelectorAll('[data-quiz-id]');
    quizItems.forEach((quizItem) => {
        const quizId = quizItem.getAttribute('data-quiz-id');
        socket.emit('joinRoom', { quizId }); 
        console.log(`Joined WebSocket room for quiz ${quizId}`);
    });
}

function likeQuiz(quizId) {
    fetch('/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `quiz_id=${quizId}&type=like`
    }).catch(error => console.error('Error during like/unlike:', error));
}

function submitComment(event, quizId) {
    event.preventDefault();
    const commentInput = document.getElementById(`comment-input-${quizId}`);
    const commentText = commentInput.value.trim();

    if (!commentText) {
        alert('Comment cannot be empty.');
        return;
    }

    fetch(`/comment_quiz/${quizId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `comment=${encodeURIComponent(commentText)}`
    }).then(response => {
        if (response.ok) {
            commentInput.value = '';
        } else {
            alert('Failed to submit comment.');
        }
    });
}

function showLikes(quizId) {
    const modal = document.getElementById(`likes-modal-${quizId}`);
    if (!modal) {
        console.error(`Modal with ID likes-modal-${quizId} not found.`);
        return;
    }
    modal.style.display = "block"; 
}

function closeLikesModal(quizId) {
    const modal = document.getElementById(`likes-modal-${quizId}`);
    if (!modal) {
        console.error(`Modal with ID likes-modal-${quizId} not found.`);
        return; 
    }
    modal.style.display = "none"; 
}

function addQuestion() {
    const questionsContainer = document.getElementById("questions-container");
    if (questionsContainer) {
        const questionCount = questionsContainer.children.length + 1; 
        const questionItem = document.createElement("div");
        questionItem.className = "question-item";
        questionItem.innerHTML = `
            <input type="text" name="questions[]" placeholder="Question ${questionCount}" required class="input-field">
            <input type="text" name="answers[]" placeholder="Choices (comma-separated)" required class="input-field">
            <input type="text" name="correct_answers[]" placeholder="Correct Answer" required class="input-field">
        `;
        questionsContainer.appendChild(questionItem);
    }
}

function showDetails(quizId){
    window.location.href = `/quiz/${quizId}`;
}

document.addEventListener('DOMContentLoaded', () => {
    initWs(); 

    const addQuestionButton = document.getElementById("add-question-button");
    if (addQuestionButton) {
        addQuestionButton.addEventListener("click", addQuestion); 
    }

    const form = document.getElementById("daily-poll-form");

    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault(); // Prevent the default form submission

            const formData = new FormData(form);
            const pollId = formData.get("poll_id"); // Get the hidden input value
            const selectedAnswer = formData.get("answer");
            fetch("/submit_poll", {
                method: "POST",
                body: JSON.stringify({
                    poll_id: pollId,
                    selected_answer: selectedAnswer
                }),
                headers: {
                    "Content-Type": "application/json",
                },
            })
                .then((response) => response.json())
                .then((data) => {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(data.message || "An error occurred while submitting your vote.");
                    }
                })
                .catch((error) => {
                    console.error("Error submitting poll:", error);
                });
            
        });
    }
});
