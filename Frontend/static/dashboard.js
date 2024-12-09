let socket = null;

function initWs() {
    const socketProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socketUrl = `${socketProtocol}://${window.location.host}`;

    socket = io(socketUrl, {
        transports: ['websocket'], 
        upgrade: false,
    });

    // Handle WebSocket connection
    socket.on('connect', () => {
        console.log("WebSocket connection established");
    });

    socket.on('disconnect', () => {
        console.log("WebSocket connection closed");
    });

    socket.on('update_times', (activeUsers) => {
        console.log("Received active users update:", activeUsers);
        updateActiveUsersList(activeUsers); 
    });

    socket.on('like_quiz', (data) => {
        const likeCountElement = document.querySelector(`#like-count-${data.quiz_id}`);
        if (likeCountElement) {
            likeCountElement.textContent = data.likes_count;
        }

        const likesList = document.getElementById(`likes-list-${data.quiz_id}`);
        if (likesList) {
            likesList.innerHTML = ''; 
            data.likes_users.forEach((user) => {
                const listItem = document.createElement('li');
                listItem.textContent = user;
                likesList.appendChild(listItem);
            });
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

    socket.on('new_comment', (data) => {
        const commentsList = document.querySelector(`#quiz-${data.quiz_id} .comments-list`);
        if (commentsList) {
            const commentHtml = `<li><strong>${data.username}</strong>: ${data.text}</li>`;
            commentsList.insertAdjacentHTML('beforeend', commentHtml);
        }
    });

    socket.on('error', (error) => {
        console.error("WebSocket error:", error);
    });
}

function showDetails(quizId){
    window.location.href = `/quiz/${quizId}`;
}

function sendActivityUpdate(userId) {
    fetch('/track_user_activity', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `user_id=${encodeURIComponent(userId)}`,
    }).catch(error => console.error('Error updating activity:', error));
}

function updateActiveUsersList(activeUsers) {
    const activeUsersList = document.getElementById('active-users-list');
    if (!activeUsersList) {
        console.error("Active users list element not found");
        return;
    }

    activeUsersList.innerHTML = ''; 

    Object.entries(activeUsers).forEach(([userId, activeTime]) => {
        const listItem = document.createElement('li');
        listItem.id = `user-${userId}`;
        listItem.textContent = `User ${userId}: ${activeTime}s active`;
        activeUsersList.appendChild(listItem);
    });
}

function likeQuiz(quizId) {
    fetch('/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `quiz_id=${encodeURIComponent(quizId)}&type=like`,
    }).catch(error => console.error('Error during like/unlike:', error));
}

function submitComment(event, quizId) {
    event.preventDefault();

    const inputElement = document.getElementById(`comment-input-${quizId}`);
    const commentText = inputElement.value.trim();

    if (!commentText) return;

    fetch('/submit_comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `quiz_id=${encodeURIComponent(quizId)}&text=${encodeURIComponent(commentText)}`,
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                inputElement.value = ''; 
            } else {
                console.error('Failed to submit comment:', data.message);
            }
        })
        .catch(error => console.error('Error submitting comment:', error));
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


function startUserActivityTracking(userId) {
    initWs();

    setInterval(() => {
        sendActivityUpdate(userId);
    }, 1000);
}



// Ensure the DOM is fully loaded before initializing
document.addEventListener('DOMContentLoaded', () => {
    const userId = document.body.dataset.userId || 'anonymous'; 
    startUserActivityTracking(userId); 

    const addQuestionButton = document.getElementById("add-question-button");
    if (addQuestionButton) {
        addQuestionButton.addEventListener("click", addQuestion); 
    }
});
