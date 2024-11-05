function addQuestion() { // Method to add multiple questions to each quiz.
    const container = document.getElementById('questions-container');

    const newQuestion = document.createElement('input');

    newQuestion.type = 'text'; // New Questions for MC Quiz 

    newQuestion.name = 'questions[]';  

    newQuestion.placeholder = 'Question'; // Temp to let user know to input questions here.

    container.appendChild(newQuestion); // Add new question to the list. 
}

function likeQuiz(quizId) { // Method that allows each user to like the post (As well as unlike it.)
    $.ajax({
        url: "/interact",
        type: "POST",
        data: {
            quiz_id: quizId,
            type: "like"
        },
        success: function(response) {
            if (response.success) {  // Onclick 
                let likeCountElement = $(`#like-count-${quizId}`);

                let currentLikeCount = parseInt(likeCountElement.text());

                if (response.action === "liked") {
                    likeCountElement.text(currentLikeCount + 1); // IF USER LIKES THE QUIZ I++ THE COUNT 
                } else {
                    likeCountElement.text(currentLikeCount - 1); // ELSE IF USER CLICKS I-- THE COUNT
                }
                
                let likesList = $(`#likes-list-${quizId}`);
                likesList.empty();
                response.likes_users.forEach(function(user) {
                    likesList.append(`<li>${$('<div/>').text(user).html()}</li>`); 
                });
            } else {
                alert(response.message || "An error occurred when liking.");
            }
        },
        error: function(xhr) {
            let errorMessage = xhr.responseJSON ? xhr.responseJSON.message : "Error try again!";

            alert(errorMessage);
        }
    });
}

function toggleLikeDropdown(quizId) { // Method that has the dropdown to see likes.
    const dropdown = $(`#like-dropdown-${quizId}`);

    dropdown.toggle(); // Onclick dropdown to display the list. 
}

function submitComment(event, quizId) {
    event.preventDefault();

    const commentInput = $(event.target).find('input');
    const commentText = $('<div/>').text(commentInput.val()).html(); 

    $.post(`/comment_quiz/${quizId}`, { comment: commentText }, function(comments) {
        const commentsList = $(`#quiz-${quizId} .comments-list`);
        commentsList.empty(); 

        comments.forEach(function(comment) {
            const commentHtml = `<li>${$('<div/>').text(comment.username).html()}: ${$('<div/>').text(comment.text).html()}</li>`;
            commentsList.append(commentHtml);
        });

        commentInput.val(''); 
    }).fail(function(xhr) {
        alert(xhr.responseJSON ? xhr.responseJSON.message : "An error occurred while submitting the comment.");
    });
}
