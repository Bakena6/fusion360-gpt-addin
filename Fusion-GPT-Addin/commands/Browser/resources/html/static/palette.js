



class Thread {
    /*
     * Assistant thread class
     * 
     */

    constructor(){

        this.textArea = document.getElementById('promptTextInput');

        // current run
        this.runId = null;

        // track number of function text boxes created
        this.nFunction  = 0;
    };

    connect() {
        const args = {  };
        adsk.fusionSendData("connect", JSON.stringify(args))
            .then((result) =>{ }); // end then
    } //end connect


    createThread() {

        // text area
        let promptTextArea = document.getElementById('promptTextInput');

        // user prompt text
        let promptTextValue = promptTextArea.value;

        const args = { promptText: promptTextValue };
        //const args = {  };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("create_thread", JSON.stringify(args))
            .then((result) =>{ }); // end then
    }// end create thread



    submitPrompt() {
        // user input text
        var textArea = document.getElementById('promptTextInput');
        var value = textArea.value;

        const args = { promptText: value };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("submit_prompt", JSON.stringify(args))
            .then((result) =>{
                //var response = JSON.parse(result);
            }); // end then

    } // end submit prompot

    /*
     * run created event
     */
    runCreated(data){
        // user input text
        var promptTextInput = document.getElementById('promptTextInput');
        var value = promptTextInput.value;

        // created with initial prompt response
        var runId = data.run_id;
        
        // Create the main newDiv element
        var runContainer = document.createElement('div'); //new div
        runContainer.className = 'run-container'; // Add class for styling
        runContainer.id = runId;
        
        //var runContainer = document.getElementById('currentRun');
        var runIdSpan = document.createElement('span');
        runIdSpan.textContent = `run: ${runId}`;
        runIdSpan.className = "span-info";
        runContainer.appendChild(runIdSpan);


        var buttonContainer = document.createElement('span');
        buttonContainer.className = 'button-container'; // Add class for flexbox styling

        var copyButton = document.createElement('button');
        copyButton.textContent = 'Copy Prompt';
        copyButton.className = 'log-button';
        copyButton.onclick = function() {
            navigator.clipboard.writeText(value);
        };
        buttonContainer.appendChild(copyButton);

        //var showHideButton = document.createElement('button');
        //showHideButton.textContent = 'Show/Hide Section';
        //showHideButton.className = 'log-button';
        //showHideButton.onclick = function() {
        //    navigator.clipboard.writeText(value);
        //};
        //buttonContainer.appendChild(showHideButton);

        runContainer.appendChild(buttonContainer);
        
        // Create the first child div for the text and the copy button
        var userText = document.createElement('div');
        userText.className = 'user-text'; // Add class for flexbox styling
        userText.textContent = value;
        runContainer.appendChild(userText);


        // Get the container and the button row
        var container = document.querySelector('.output-container');

        // Insert the new div after the button row
        //container.insertBefore(runContainer, promptTextInput);
        container.prepend(runContainer);

        // Optional: Clear the textarea after submitting
        promptTextInput.value = '';
    }// end create run

    /*
     *  display streaming output from OpenAI assistant api
     */
    stepCreated(data){
        let runId = data.run_id;
        var runContainer = document.getElementById(runId);
        var eventType = data.event;
        
        // tool calls or message created
        var stepType = data.step_type;

        // container for message/ tool call response
        var stepContainer = document.createElement('div');
        stepContainer.className = "step-container";
        stepContainer.id = stepType;

        // step type and id info
        var idSpan = document.createElement('div');
        idSpan.className = "span-info";
        idSpan.innerHTML = `${stepType}: ${data.step_id}`;
        stepContainer.appendChild(idSpan);

        // start message
        if (stepType == "message_creation"){
            this.messageContainer = document.createElement('span');
            this.messageContainer.className = "message-container";
            stepContainer.appendChild(this.messageContainer);

            // start toolcalls
        } else if ( stepType == "tool_calls"){

            this.toolContainer = document.createElement('div');
            this.toolContainer.className = "tool-container";
            stepContainer.appendChild(this.toolContainer);

        }// end if


        runContainer.appendChild(stepContainer);

    }// end create message


    /*
     *  display streaming output from OpenAI assistant api
     */
    messageCreated(data){
        //this.messageContainer.textContent = this.messageSpan.textContent + content;
    }// end update message


    /*
     *  display streaming output from OpenAI assistant api
     */
    messageDelta(data){
        let content = data.message;
        this.messageContainer.textContent = this.messageContainer.textContent + content;
    }// end update message


    /*
     *  display streaming output from OpenAI assistant api toolcall
     */
    stepDelta(data){

        let content;

        var function_name = data.function_name;
        var function_args = data.function_args;
        var function_output = data.function_output;

        // function name should be in first part of function delta return
        if (function_name != null){

            var functionContainer = document.createElement('div');
            var functionNameEl = document.createElement('span');

            functionNameEl.className = "function-name";
            functionNameEl.textContent= `${function_name}`;

            // keep function body
            this.nFunction += 1;
            var functionArgsEl = document.createElement('textarea');
            var functionArgsId = `functionArgs_${this.nFunction}`;

            functionArgsEl.id = functionArgsId;
            functionArgsEl.className = 'functionBody';
            functionArgsEl.rows = 1;
            this.functionArgsEl = functionArgsEl;

            var runFunctionBotton = document.createElement('button');
            runFunctionBotton.textContent = 'Run Function';
            runFunctionBotton.className = "log-button";

            // re run the function call
            runFunctionBotton.onclick = function() {
                var functionArgs = document.getElementById(functionArgsId);
                var args = {
                    "function_name": function_name,
                    "function_args": functionArgs.value
                }
                adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
                    .then((result) =>{ }); // end then
            };// end click

            functionContainer.appendChild(functionNameEl);
            functionContainer.appendChild(runFunctionBotton);
            functionContainer.appendChild(functionArgsEl);

            this.toolContainer.appendChild(functionContainer);


        } else if (function_args != null){
            content = `${function_args}`;

            var existingText = this.functionArgsEl.textContent;

            this.functionArgsEl.style.height = 'auto';
            this.functionArgsEl.style.height = this.functionArgsEl.scrollHeight + 'px';

            this.functionArgsEl.textContent = existingText + content;
            

        } else if (function_output != null){
            content = `${function_output}`;
        };


    } // end update message


} // end thread



let thread = new Thread();




function uploadTools() {
    const args = { };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("upload_tools", JSON.stringify(args))
        .then((result) =>{ }); // end then
} // end uploadTools



function executeToolCall(function_name) {
    // text area
    const functionArgInputs = document.querySelectorAll(`.${function_name}__input`);
    let function_args = {};
    for (let i=0; i < functionArgInputs.length; i++) {
            const name = functionArgInputs[i].name;
            const val = functionArgInputs[i].value;
            function_args[name] = JSON.parse(val);
        };

    const args = {"function_name": function_name, "function_args": function_args };

    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
        .then((result) =>{ }); // end then

} // end executeToolCall

function getTools() {

    const args = {  };
    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("get_tools", JSON.stringify(args))
        .then((result) =>{ 

            let toolTestContainer = document.getElementById('toolTestContainer');

            toolTestContainer.innerHTML = "";

            let response = JSON.parse(result);

            for (const [m_name, params] of Object.entries(response)) {

                let toolRow = document.createElement("div");
                toolRow.id = `${m_name}_row`;
                console.log(params);

                let functionButton = document.createElement("button");
                functionButton.innerHTML = m_name;
                functionButton.type = "button";
                functionButton.id = m_name;
                functionButton.setAttribute("onClick", `javascript: executeToolCall("${m_name}");`);
                functionButton.className = "toolCallButton";
                const inputContainer = document.createElement("span");

                for (const [param_name, param_info] of Object.entries(params)) {
                    const paramInput = document.createElement("input");

                    const paramDefault = param_info.default_val;

                    paramInput.id = `${m_name}__${param_name}`;
                    paramInput.name = `${param_name}`;

                    paramInput.className = `${m_name}__input`;
                    paramInput.placeholder = `${param_name}`;

                    //console.log("paramDefault", paramDefault);
                    paramInput.value = JSON.stringify(paramDefault);

                    inputContainer.appendChild(paramInput);
                };

                //responseDiv.className = 'message-response'; // Add class for styling
                toolRow.appendChild(functionButton);
                toolRow.appendChild(inputContainer);
                toolTestContainer.appendChild(toolRow);


            }// end for

        }); // end then
} // end getTools

//function

function hideTools() {

    let toolTestContainer = document.getElementById('toolTestContainer');

    toolTestContainer.innerHTML = "";

} // end hide tools

 function getWindowHeight() {
      return window.innerHeight;
    }

    // Listen for the window resize event
    window.addEventListener('resize', function() {
      const height = getWindowHeight();
      console.log("Current window height:", height);
      
      // You can call other functions or update the DOM here
      // e.g., update a span with the height, etc.
    });

    // Optional: Log the initial height on page load
    console.log("Initial window height:", getWindowHeight());


window.fusionJavaScriptHandler = {

    handle: function (action, messageString) {
        //console.log("from js");
        try {
            // Message is sent from the add-in as a JSON string.
            const messageData = JSON.parse(messageString);

            if (action === "updateSelection") {
                thread.updateSelection(messageData);

            } else if (action === "runCreated") {
                thread.runCreated(messageData);

            } else if (action === "stepCreated") {
                thread.stepCreated(messageData);

            } else if (action === "messageCreated") {
                thread.messageCreated(messageData);

            } else if (action === "messageDelta") {
                thread.messageDelta(messageData);

            } else if (action === "stepDelta") {
                thread.stepDelta(messageData);

            } else if (action === "debugger") {
                debugger;
            } else {
                return `Unexpected command type: ${action}`;
            }

        } catch (e) {
            console.log("error")
            adsk.fusionSendData("error", JSON.stringify(e))
            console.log(e);
            console.log(`Exception caught with command: ${action}, data: ${data}`);

        }
        //return "OK";
    },
};













