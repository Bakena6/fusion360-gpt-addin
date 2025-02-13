



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


        // set function args height
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






function executeToolCall(function_name) {
    // text area
    const functionArgInputs = document.querySelectorAll(`.${function_name}__input`);

    let function_args = {};
    for (let i=0; i < functionArgInputs.length; i++) {
        const name = functionArgInputs[i].name;
        const val = functionArgInputs[i].value;
        //console.log(val);
        function_args[name] = JSON.parse(val);
    };

    const args = {"function_name": function_name, "function_args": function_args };

    // Send the data to Fusion as a JSON string. The return value is a Promise.
    adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
        .then((result) =>{ }); // end then

} // end executeToolCall


function setWindowHeight() {

    let outputContainer = document.getElementById('outputContainer');
    let toolTestContainer = document.getElementById('toolTestContainer');
    let inputContainer = document.getElementById('inputContainer');

    let outputHeight = outputContainer.offsetHeight;
    let toolTestHeight = toolTestContainer.offsetHeight;
    let inputHeight = inputContainer.offsetHeight;

    //console.log("Current outputContainer height:", outputHeight);
    //console.log("Current toolTestContainer height:", toolTestHeight);
    //console.log("Current inputContainer height:", inputHeight);

    let newOutputHeight = window.innerHeight - (inputHeight + toolTestHeight +5) ;
    outputContainer.style.height = `${newOutputHeight}px`;


} // end setWindowHeight





class Control{

    constructor(){

        this.textArea = document.getElementById('promptTextInput');


        // Listen for the window resize event
        window.addEventListener('resize', function() {
            setWindowHeight();
            // You can call other functions or update the DOM here
            // e.g., update a span with the height, etc.
        });


        this.display_tools = false;
        window.addEventListener('load', (event) => {
          // Your code to execute after the page loads
            setWindowHeight();


        });

        //this.createToolElements();
        this.tools = [];


    //this.toolsContainer();
    }; // end constructor



    //async loadTools(){ };

     async toggleTools() {

         if (this.tools.length == 0){
            this.tools = await this.getTools();
            this.createToolElements();
        } else{

            this.showHideElement("toolTestContainer");
        };

        setWindowHeight();

    } // end hide tools


    showHideElement(elementId){

        let element = document.getElementById(elementId);
        if (element.style.display === "none") {
            element.style.display = "block"; 
        } else {
            element.style.display = "none"; 
        }

    }; // end showHideElement










     uploadTools() {
        const args = { };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("upload_tools", JSON.stringify(args))
            .then((result) =>{ }); // end then
    } // end uploadTools




    /*
    * get availible tool call from Python class
    */
     async getTools() {

        const args = {  };

         var result = await adsk.fusionSendData("get_tools", JSON.stringify(args));

         var resultJson = await JSON.parse(result);

        return resultJson;


    } // end reload

    get_current_cb_val(){

        const settingCbs = document.querySelectorAll('.settingCb');

        settingCbs.forEach(cb => {
            const args = {
                "setting_name": cb.id,
                "setting_val": cb.checked
            };
            adsk.fusionSendData("cb_change", JSON.stringify(args)).then((result) =>{ });

        }); // end for each

    };// end get_current_cb


    reloadModules(){
        const args = { };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        // include current checkbox settings
        adsk.fusionSendData("reload_modules", JSON.stringify(args))
            .then((result) =>{ 
                this.get_current_cb_val();
            }); // end then
    };

    reconnect(){
        const args = { };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("reconnect", JSON.stringify(args))
            .then((result) =>{ }); // end then
    };



    createToolElements() {

        let toolTestContainer = document.getElementById('toolTestContainer');
        toolTestContainer.innerHTML = "";
        //let response = 
        // class name, methods

        for (const [c_name, methods] of Object.entries(this.tools)) {


            // methods
            // top class container
            const toolClassContainer = document.createElement("div");
            toolClassContainer.className = "toolClassContainer";

            //const classSectionTitle = document.createElement("span");
            const classSectionTitle = document.createElement("button");
            classSectionTitle.innerHTML = c_name;
            classSectionTitle.type = "button";
            classSectionTitle.className = "toolCallClassTitle";


            // all methods in a class
            const methodsContainer = document.createElement("div");
            const methodsContainerId = `${c_name}_method_container`;
            methodsContainer.id = methodsContainerId;
            methodsContainer.className = "methodsContainer";
            methodsContainer.style.display = "none";

            classSectionTitle.onclick = function() {
                //showHideElement(methodsContainerId);
                let element = document.getElementById(methodsContainerId);
                if (element.style.display === "none") {
                    element.style.display = "block"; 
                } else {
                    element.style.display = "none"; 
                }



            };

            toolClassContainer.appendChild(classSectionTitle);

            let borderColor="pink";

            if (c_name == "CreateObjects"){
                borderColor = "green";

            } else if (c_name == "ModifyObjects") {
                borderColor = "orange";

            } else if (c_name == "Sketches") {
                borderColor = "green";

            } else if (c_name == "DeleteObjects") {
                borderColor = "red";
            };


            toolClassContainer.style.borderColor = borderColor;

            for (const [m_name, params] of Object.entries(methods)) {

                const toolRow = document.createElement("div");
                toolRow.className = 'tool-row';

                const functionButton = document.createElement("button");
                functionButton.innerHTML = m_name;
                functionButton.type = "button";
                functionButton.id = m_name;
                functionButton.setAttribute("onClick", `javascript: executeToolCall("${m_name}");`);
                functionButton.className = "toolCallButton";

                const inputContainer = document.createElement("span");
                inputContainer.className = "functionInputContainer";

                // params
                for (const [param_name, param_info] of Object.entries(params)) {
                    //const paramInput = document.createElement("input");
                    const paramInput = document.createElement("textarea");

                    const paramDefault = param_info.default_val;
                    paramInput.id = `${m_name}__${param_name}`;
                    paramInput.name = `${param_name}`;
                    paramInput.rows = 1;
                    paramInput.wrap = "hard";
                    //paramInput.type = "text";
                    paramInput.className = `${m_name}__input param_input`;
                    paramInput.placeholder = `${param_name}`;

                    paramInput.value = JSON.stringify(paramDefault);

                    this.resizeInput(paramInput);

                    function autoResizeTextarea(textarea) {
                        textarea.style.height = "auto"; // Reset the height
                        textarea.style.height = textarea.scrollHeight + "px"; // Set height to scroll height
                    }

                    paramInput.addEventListener("click", () => autoResizeTextarea(paramInput));

                    inputContainer.appendChild(paramInput);

                };

                //responseDiv.className = 'message-response'; // Add class for styling
                toolRow.appendChild(functionButton);
                toolRow.appendChild(inputContainer);
                methodsContainer.appendChild(toolRow);

            }// end for params

            toolClassContainer.appendChild(methodsContainer);

            toolTestContainer.appendChild(toolClassContainer);


        }// end for


        toolTestContainer.style.height = '50%';

        setWindowHeight();

    } // end getTools

    //function

    record(){

        let recordButton = document.getElementById('recordButton');
        recordButton.style.backgroundColor = "gray";
        if ( recordButton.textContent == "Start Record"){
            const args = {  };
            adsk.fusionSendData("start_record", JSON.stringify(args)).then((result) =>{ 

                recordButton.style.backgroundColor = "red";
                recordButton.textContent = "Recording";

            });



        } else {

            recordButton.textContent = "Transcribing...";
            const args = {  };
            // Send the data to Fusion as a JSON string. The return value is a Promise.
            adsk.fusionSendData("stop_record", JSON.stringify(args))
                .then((result) =>{ 

                    recordButton.style.backgroundColor = "green";
                    recordButton.textContent = "Start Record";

                    let response = JSON.parse(result);
                    let audio_text = response["content"];
                    console.log(audio_text)

                    var promptTextInput = document.getElementById('promptTextInput');
                    promptTextInput.value = promptTextInput.value + " " + audio_text;

                });


        }; // end else


    }; // end start record



    resizeInput(input) {
        input.style.width = (5 +input.value.length) + "ch"; // Adjust multiplier for better spacing


    } // end resize


} // end control container



function send_cp_val(cb_event){

    const args = {
        "setting_name": cb_event.target.id,
        "setting_val": cb_event.target.checked
    };

    adsk.fusionSendData("cb_change", JSON.stringify(args))
        .then((result) =>{ });
};





// settings check boxes
window.addEventListener('load', (event) => {

    //debugCb = document.getElementById('debugCb');

    const settingCbs = document.querySelectorAll('.settingCb');

    settingCbs.forEach(cb => {

        cb.addEventListener("change", (cb_event) => send_cp_val(cb_event));

    }); // end for each





});



let control = new Control();



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
            adsk.fusionSendData("error", JSON.stringify(e))
            console.log(e);
            console.log(`Exception caught with command: ${action}, data: ${data}`);

        }
        //return "OK";
    },
};













