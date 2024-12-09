function handleChoice(selectedChoice, correctAnswer, element) {
    const choicesList = element.parentElement;

    Array.from(choicesList.children).forEach((choiceElement) => {
        const choiceText = choiceElement.innerText;

        if (choiceText === correctAnswer) {
            choiceElement.style.color = "green";
        } else if (choiceText === selectedChoice) {
            choiceElement.style.color = "red";
        } else {
            choiceElement.style.color = "gray";
        }
    });
    choicesList.style.pointerEvents = "none";
}