




function createThread() {

    // text area
    var promptTextArea = document.getElementById('promptTextInput');
    
    // user prompt text
    var promptTextValue = promptTextArea.value;

    const args = { promptText: promptTextValue };
    //const args = {  };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("create_thread", JSON.stringify(args))
        .then((result) =>{ }); // end then

}



function submitPrompt() {
    var textArea = document.getElementById('promptTextInput');
    var value = textArea.value;

    // Create the main newDiv element
    var newDiv = document.createElement('div');
    newDiv.className = 'text-output'; // Add class for styling

    // Create the first child div for the text and the copy button
    var textDiv = document.createElement('div');
    textDiv.className = 'text-with-copy'; // Add class for flexbox styling

    var textSpan = document.createElement('span');
    textSpan.textContent = value;
    textDiv.appendChild(textSpan);

    var copyButton = document.createElement('button');
    copyButton.textContent = 'Copy';
    copyButton.onclick = function() {
        navigator.clipboard.writeText(value);
    };
    textDiv.appendChild(copyButton);

    // Create the second child div for the message response
    var responseDiv = document.createElement('div');
    responseDiv.textContent = 'None';
    responseDiv.className = 'message-response'; // Add class for styling

    const args = { promptText: value };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("submit_prompt", JSON.stringify(args))
        .then((result) =>{
            var response = JSON.parse(result);
            responseDiv.textContent = response['resp_val']
        }); // end then

    // Append both child divs to the main div
    newDiv.appendChild(textDiv);
    newDiv.appendChild(responseDiv);

    // Get the container and the button row
    var container = document.querySelector('.input-container');
    var buttonRow = container.querySelector('.button-row');

    // Insert the new div after the button row
    container.insertBefore(newDiv, buttonRow.nextSibling);

    // Optional: Clear the textarea after submitting
    textArea.value = '';
}







function runLast() {
    // text area
    const args = {  };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("run_last", JSON.stringify(args))
        .then((result) =>{ }); // end then

} // end get sheets


function testTools() {

    // text area
    var promptTextArea = document.getElementById('promptTextInput');
    
    // user prompt text
    var promptTextValue = promptTextArea.value;

    const args = { promptText: promptTextValue };
    //const args = {  };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("test_tools", JSON.stringify(args))
        .then((result) =>{ }); // end then

} // end get sheets


function getSteps() {
    // text area
    const args = {  };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("get_steps", JSON.stringify(args))
        .then((result) =>{ }); // end then

} // end get sheets





window.fusionJavaScriptHandler = {
    handle: function (action, messageString) {
        console.log("from js");
        try {
            // Message is sent from the add-in as a JSON string.
            const messageData = JSON.parse(messageString);
            if (action === "updateMessage") {
                updateMessage(messageData);
            } else if (action === "updateSelection") {
                updateSelection(messageData);
            } else if (action === "debugger") {
                debugger;
            } else {
                return `Unexpected command type: ${action}`;
            }
        } catch (e) {

            adsk.fusionSendData("error", JSON.stringify(e))
            console.log(e);
            console.log(`Exception caught with command: ${action}, data: ${data}`);



        }
        return "OK";
    },
};













