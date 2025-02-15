

class Thread {
    /*
     * Assistant thread class
     * 
     */

    constructor(){
        this.promptTextInput = document.getElementById('promptTextInput');
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
        var value = promptTextInput.value;

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


    toggleSectionVis(event, elementId){

        console.log("toggle section vis");
        let button = event.target;
        let element = document.getElementById(elementId);

        if (element.style.display === "none") {
            element.style.display = "block"; 
            button.textContent = "Hide";
        } else {
            element.style.display = "none"; 
            button.textContent = "Show";
        } // end if else

    };


    runCreated(data){
        // user input text
        //var promptTextInput = document.getElementById('promptTextInput');
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

        var buttonContainer = document.createElement('span');
        buttonContainer.className = 'button-container'; // Add class for flexbox styling
        
        // contains message and tool call responses
        var responseContainer = document.createElement('div');
        responseContainer.className = `response-container`;
        responseContainer.id = `response_${runId}`;

        var showHideButton = document.createElement('button');
        showHideButton.textContent = "Show/Hide Section";
        showHideButton.className = "log-button ";
        showHideButton.onclick = (event) =>{this.toggleSectionVis(event, responseContainer.id)};

        buttonContainer.appendChild(showHideButton);

        //var copyButton = document.createElement('button');
        //copyButton.textContent = 'Copy Prompt';
        //copyButton.className = 'log-button';
        //copyButton.onclick = function() {
        //    navigator.clipboard.writeText(value);
        //};
        //buttonContainer.appendChild(copyButton);

        runContainer.appendChild(buttonContainer);

        runContainer.appendChild(runIdSpan);


        // Create the first child div for the text and the copy button
        var userText = document.createElement('div');
        userText.className = 'user-text'; // Add class for flexbox styling
        userText.textContent = value;
        runContainer.appendChild(userText);
        runContainer.appendChild(responseContainer);

        // Get the container and the button row
        var container = document.querySelector('.output-container');
        
        // Insert the new div after the button row
        container.prepend(runContainer);

        // Optional: Clear the textarea after submitting
        promptTextInput.value = '';

    }// end runCreated

    /*
     *  step created
     */
    stepCreated(data){
        var runId = data.run_id;

        //var runContainer = document.getElementById(runId);
        var responseContainer = document.getElementById(`response_${runId}`);

        var eventType = data.event;
        
        // tool calls or message created
        var stepType = data.step_type;
        var stepId = data.step_id;
        
        // container for message/ tool call response
        var stepContainer = document.createElement('div');
        stepContainer.className = "step-container";
        stepContainer.id = stepType;


        // step type and id info
        var idSpan = document.createElement('span');
        idSpan.className = "span-info";
        idSpan.innerHTML = `${stepType}: ${stepId}`;

        var toggleContainerId = `message_step__${stepId}`;
        
        var showHideButton = document.createElement('button');
        showHideButton.textContent = "Show/Hide Step";
        showHideButton.className = "log-button";
        showHideButton.onclick = (event) =>{this.toggleSectionVis(event, toggleContainerId)};
        stepContainer.appendChild(showHideButton);
        stepContainer.appendChild(idSpan);
       

        // start message
        if (stepType == "message_creation"){
            this.messageContainer = document.createElement('span');
            this.messageContainer.className = "message-container";
            this.messageContainer.id = toggleContainerId;
            stepContainer.appendChild(this.messageContainer);

            // start toolcalls
        } else if ( stepType == "tool_calls"){
            this.toolContainer = document.createElement('div');
            this.toolContainer.className = "tool-container";
            this.toolContainer.id = toggleContainerId;
            stepContainer.appendChild(this.toolContainer);

        }// end if


        //runContainer.appendChild(stepContainer);
        responseContainer.appendChild(stepContainer);

    }// end stepCreated


    /*
     *  step created
     */
    messageCreated(data){
        //this.messageContainer.textContent = this.messageSpan.textContent + content;

    }// end messageCreated


    /*
     *  display streaming output from OpenAI assistant API, message
     */
    messageDelta(data){
        let content = data.message;
        this.messageContainer.textContent = this.messageContainer.textContent + content;

    }// end messageDelta

    /*
     *  display streaming output from OpenAI assistant API, toolcall
     */
    stepDelta(data){

        let content;
        var function_name = data.function_name;

        var tool_call_id = data.tool_call_id;

        var function_args = data.function_args;
        var function_output = data.function_output;

        // function name should be in first part of function delta return
        if (function_name != null){

            var functionContainer = document.createElement('div');
            functionContainer.className = "function-container";

            //var functionNameEl = document.createElement('span');
            //functionNameEl.className = "function-name";
            //functionNameEl.textContent= `${function_name}`;

            // keep function body
            this.nFunction += 1;
            var functionArgsEl = document.createElement('textarea');
            var functionArgsId = `functionArgs_${this.nFunction}`;

            functionArgsEl.id = functionArgsId;
            functionArgsEl.className = 'functionBody';
            functionArgsEl.rows = 1;
            this.functionArgsEl = functionArgsEl;

            var runFunctionButton = document.createElement('button');
            runFunctionButton.textContent = `${function_name}`;
            runFunctionButton.className = "function-name";

            // re run the function call
            runFunctionButton.onclick = function() {
                var functionArgs = document.getElementById(functionArgsId);
                var args = {
                    "function_name": function_name,
                    "function_args": functionArgs.value
                }
                adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
                    .then((result) =>{ }); // end then
            };// end click


            //functionContainer.appendChild(functionNameEl);
            functionContainer.appendChild(runFunctionButton);

            if (tool_call_id != null){
                var idSpan = document.createElement("div");
                idSpan.className = "span-info";
                idSpan.innerHTML = `tool_call: ${tool_call_id}`;
                functionContainer.appendChild(idSpan);
            };

            functionContainer.appendChild(functionArgsEl);

            this.functionContainer = functionContainer;
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

    } // end stepDelta


    /*
     *  display competed tool call result
     */
    toolCallResponse(data){


        var tool_call_id = data.tool_call_id;
        var function_result = data.function_result;

        var functionResults = document.createElement('div');
        functionResults.className = "function-results";
        functionResults.id = `result__${tool_call_id}`;

        var showHideButton = document.createElement('button');
        showHideButton.textContent = "Show/Hide Section";
        showHideButton.className = "log-button";
        showHideButton.onclick = (event) =>{this.toggleSectionVis(event, functionResults.id )};


        functionResults.textContent = function_result;

        var idSpan = document.createElement("div");
        idSpan.className = "span-info";
        idSpan.innerHTML = `tool_call: ${tool_call_id}`;

        this.functionContainer.appendChild(showHideButton);
        this.functionContainer.appendChild(idSpan);
        this.functionContainer.appendChild(functionResults);



    }// end toolCallResponse



} // end thread




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



function setWindowHeight() {

    let tabContainer = document.getElementById('tabContainer');
    let pageContent = document.getElementById('pageContent');
    //

    let toolTestContainer = document.getElementById('toolTestContainer');
    let inputContainer = document.getElementById('inputContainer');
    let consoleOutput = document.getElementById('consoleOutput');

    let tabContainerHeight = tabContainer.offsetHeight;
    let inputContainerHeight = inputContainer.offsetHeight;
    let consoleOutputHeight = consoleOutput.offsetHeight;

    let newOutputHeight = window.innerHeight - (tabContainerHeight + inputContainerHeight + consoleOutputHeight +20) ;
    pageContent.style.height = `${newOutputHeight}px`;


} // end setWindowHeight





class Control{

    constructor(thread){

        this.thread = thread;
        // input text area
        this.promptTextArea = document.getElementById('promptTextInput');

        this.pageContent = document.getElementById('pageContent');
        //let toolTestContainer = document.getElementById('toolTestContainer');
        this.tabContent = document.getElementById('tabContainer');
        this.inputContainer = document.getElementById('inputContainer');

        this.outputContainer = document.getElementById('outputContainer');
        this.toolTestContainer = document.getElementById('toolTestContainer');

        this.submitOnEnter = true;



        //this.createToolElements();
        this.tools = [];

        this.connectInputs();

        setWindowHeight();

    }; // end constructor


     send_cp_val(cb_event){
        const args = {
            "setting_name": cb_event.target.id,
            "setting_val": cb_event.target.checked
        };
        adsk.fusionSendData("cb_change", JSON.stringify(args))
            .then((result) =>{ });
    };


    connectInputs(){
        console.log("connectInputs");

        //debugCb = document.getElementById('debugCb');

        window.addEventListener("resize", (event) => {setWindowHeight()});

        const settingCbs = document.querySelectorAll('.settingCb');
        settingCbs.forEach(cb => {
            cb.addEventListener("change", (cb_event) => this.send_cp_val(cb_event));
        }); // end for each

        // change prompt text size
        const textSizeInput = document.getElementById('textSizeInput');
        textSizeInput.addEventListener("change", (event) => {
            const fontSize = event.target.value;
            this.promptTextArea.style.fontSize = fontSize;
            setWindowHeight();
        });

        const submitOnEnterInput = document.getElementById('submitOnEnter');
        submitOnEnterInput.addEventListener("change", (event) => {
            this.submitOnEnter = event.target.checked;
            console.log(this.submitOnEnter);
        });

        // submit prompt on ender
        this.promptTextArea.addEventListener('keydown', (event) => {
            if ((event.key === 'Enter') && (this.submitOnEnter == true)){
                event.preventDefault(); // Prevent the default action (form submission)
                //this.promptTextArea.value += '*'; // Add an asterisk to the input field
                this.thread.submitPrompt()
            } // end if

        });// end submit on enter 

    }; // end connect inputs



     async toggleTools() {
         if (this.tools.length == 0){
            this.tools = await this.getTools();
            this.createToolElements();
        };

    } // end hide tools


    /*
     * change tab
    * */
    changeTab(tabIndex){

        let tabs  = document.querySelectorAll(".contentTab");
        let tabButtons = document.querySelectorAll(".tab-button");

        for (let i=0; i < tabs.length; i++) {

            let element = tabs[i];
            let buttonElement = tabButtons[i];

            if (i == tabIndex) {
                element.style.display = "block"; 

                buttonElement.style.backgroundColor = "#262626"; 
                buttonElement.style.color = "magenta"; 
                this.toggleTools();

            } else {
                element.style.display = "none"; 

                buttonElement.style.color = "white"; 
                buttonElement.style.backgroundColor = "#878787"; 

            }; //end if

        setWindowHeight();

        };// end for

    }; // end showHideElement


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

    reloadFusionIntf(){
        const args = { };
        // include current checkbox settings
        adsk.fusionSendData("reload_fusion_intf", JSON.stringify(args))
            .then((result) =>{ 
                this.get_current_cb_val();
            }); // end then
    };

    resetAll(){
        const args = { };
        this.outputContainer.innerHTML = ""
        this.toolTestContainer.innerHTML = ""
        adsk.fusionSendData("reset_all", JSON.stringify(args)) .then((result) =>{ }); // end then
    };

    reconnect(){
        const args = { };
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("reconnect", JSON.stringify(args))
            .then((result) =>{ }); // end then
    }; // end reconnect

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


        //toolTestContainer.style.height = '100%';

        setWindowHeight();

    } // end getTools

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

                    var promptTextInput = document.getElementById('promptTextInput');
                    promptTextInput.value = promptTextInput.value + " " + audio_text;

                });


        }; // end else
    }; // end start record

    resizeInput(input) {
        input.style.width = (5 +input.value.length) + "ch"; // Adjust multiplier for better spacing

    } // end resize


} // end control container







let thread;
let control;
window.addEventListener('load', (event) => { 

    thread = new Thread();

    control = new Control(thread);

});// end window on load







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

            } else if (action === "toolCallResponse") {
                thread.toolCallResponse(messageData);
            } else if (action === "print") {
                console.log(messageData);

            } else if (action === "debugger") {
                debugger;

            } else {

                return `Unexpected command type: ${action}`;
            }

        } catch (e) {
            adsk.fusionSendData("error", JSON.stringify(e))
            console.log(e);
            console.log(`Exception caught with command: ${action}, data: ${messageData}`);

        }
        //return "OK";
    },
};













