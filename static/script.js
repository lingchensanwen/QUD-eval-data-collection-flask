function highlightLine(lineNumber) {
    var line = document.getElementById('line' + lineNumber);
    // Remove highlight from previously highlighted line
    var highlightedLine = document.querySelector('.highlight-line');
    if (highlightedLine) {
        highlightedLine.classList.remove('highlight-line');
    }
    // Add highlight to the current line
    line.classList.add('highlight-line');
}
function highlightQuestion(radio) {
    var question = radio.closest(".question");
    question.classList.add("question-highlight");
}