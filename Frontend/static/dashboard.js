function addQuestion() { // Method to add multiple questions to each quiz.
    const container = document.getElementById('questions-container');
    const currentQuestionNumber = container.children.length + 1;
    const question = document.createElement('div');


    const newQuestion = document.createElement('input');
    newQuestion.required = true
    newQuestion.type = 'text'; // New Questions for MC Quiz 
    newQuestion.name = 'questions[]';  
    newQuestion.placeholder = `Question ${currentQuestionNumber}`; // Temp to let user know to input questions here.
    question.appendChild(newQuestion); // Add new question to the list. 

    const newChoices = document.createElement('input');
    newChoices.required = true
    newChoices.type = 'text'; // New Questions for MC Quiz 
    newChoices.name = 'answers[]';  
    newChoices.placeholder = 'Choices (csv) *'; // Temp to let user know to input questions here.
    question.appendChild(newChoices); // Add new question to the list.

    const newCorrectAnswer = document.createElement('input');
    newChoices.required = true
    newCorrectAnswer.type = 'text'; // New Questions for MC Quiz 
    newCorrectAnswer.name = 'correct_answers[]';  
    newCorrectAnswer.placeholder = 'Correct Answer *'; // Temp to let user know to input questions here.
    question.appendChild(newCorrectAnswer); // Add new question to the list. 

    container.appendChild(question);

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

function submitComment(event, quizId) { // NEDS WORK
    event.preventDefault();

    const commentText = $('<div/>').text($(event.target).find('input').val()).html();

    $.post(`/comment_quiz/${quizId}`, { comment: commentText }, function(comments) {

        const lastComment = comments[comments.length - 1];

        const commentHtml = `<li>${$('<div/>').text(lastComment.username).html()}: ${$('<div/>').text(lastComment.text).html()}</li>`;
        
        $(`#quiz-${quizId} .comments-list`).append(commentHtml);
        
        $(event.target).find('input').val('');
    });
}

function showDetails(quizId){
    window.location.href = `/quiz/${quizId}`;
}