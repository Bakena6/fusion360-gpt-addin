

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
        const args = { function_name: "connect"};
        adsk.fusionSendData("function_call", JSON.stringify(args))
            .then((result) =>{ }); // end then
    } //end connect

    createThread() {
        // text area
        let promptTextArea = document.getElementById('promptTextInput');
        // user prompt text
        let promptTextValue = promptTextArea.value;
        const args = { promptText: promptTextValue };
        
        // Send the data to Fusion as a JSON string. The return value is a Promise.
        adsk.fusionSendData("create_thread", JSON.stringify(args)).then((result) =>{ }); // end then

    }// end create thread


    scrollToBottom(){
        let wrapper = document.getElementById("pageWrapper");
        wrapper.scrollTop = wrapper.scrollHeight;
    };

    submitPrompt() {
        this.scrollToBottom();   
        // user input text
        var value = promptTextInput.value;

        const args = {
            function_name: "send_message", 
            function_args: {message: value} 
        };
        adsk.fusionSendData("function_call", JSON.stringify(args))
            .then((result) =>{ }); // end then

    } // end submit prompot


    /*
    * run created event
    */
    toggleSectionVis(event, elementId){

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
        container.append(runContainer);

        // Optional: Clear the textarea after submitting
        promptTextInput.value = '';

        this.scrollToBottom();
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

        // contains buttons, item id
        var logHeader = document.createElement('div');
        logHeader.className = "log-header"

        // step type and id info
        var idSpan = document.createElement('span');
        idSpan.className = "span-info";
        idSpan.innerHTML = `${stepType}: ${stepId}`;

        var toggleContainerId = `message_step__${stepId}`;
        
        var showHideButton = document.createElement('button');
        showHideButton.textContent = "Hide";
        showHideButton.className = "log-button";
        showHideButton.onclick = (event) =>{this.toggleSectionVis(event, toggleContainerId)};

        logHeader.appendChild(showHideButton);
        logHeader.appendChild(idSpan);
        stepContainer.appendChild(logHeader);
       

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

        responseContainer.appendChild(stepContainer);
        this.scrollToBottom();

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
        this.scrollToBottom();   

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
            
            // contains buttons, item id
            var logHeader = document.createElement('div');
            logHeader.className = "log-header"

            // keep function body
            this.nFunction += 1;
            var functionArgsEl = document.createElement('textarea');
            var functionArgsId = `functionArgs_${this.nFunction}`;

            functionArgsEl.id = functionArgsId;
            functionArgsEl.className = 'function-body-textarea';
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
                    "function_args": functionArgs.value,
                    "tool_call_id": tool_call_id
                }
                adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
                    .then((result) =>{ }); // end then
            };// end click


            logHeader.appendChild(runFunctionButton);

            // tool call id should be passed with first delta,
            // we use this is to write the function results in the correct div
            if (tool_call_id != null){
                var idSpan = document.createElement("span");
                idSpan.className = "span-info";
                idSpan.innerHTML = `tool_call_start: ${tool_call_id}`;
                logHeader.appendChild(idSpan);

                // create the function results container when the function call starts
                // this way the result container exists when the results are run, rerun
                var functionResults = document.createElement('div');
                functionResults.className = "function-results";
                functionResults.id = `result_container__${tool_call_id}`;
                
                // <pre> for displaying pretty json
                var resultsJson = document.createElement('pre');
                resultsJson.id = `result__${tool_call_id}`;
                resultsJson.innerHTML = "Pending...";
                // json output
                functionResults.appendChild(resultsJson);

                // contains buttons, item id
                var resultsLogHeader = document.createElement('div');
                resultsLogHeader.className = "log-header log-response-header"


                var showHideButton = document.createElement('button');
                showHideButton.textContent = "Hide";
                showHideButton.className = "log-button";
                showHideButton.onclick = (event) =>{this.toggleSectionVis(event, functionResults.id )};

                // clear outputs
                var clearResultButton = document.createElement('button');
                clearResultButton.textContent = "Clear";
                clearResultButton.className = "log-button";
                clearResultButton.onclick = (event) =>{
                    resultsJson.innerHTML="";
                };

                // tool call response id
                var resultsIdSpan = document.createElement("span");
                resultsIdSpan.className = "span-info";
                resultsIdSpan.innerHTML = `${tool_call_id}`;

                resultsLogHeader.appendChild(showHideButton);
                resultsLogHeader.appendChild(clearResultButton);
                resultsLogHeader.appendChild(idSpan);


            };

            // tool call name/argument
            functionContainer.appendChild(logHeader);
            functionContainer.appendChild(functionArgsEl);

            // tool call response
            functionContainer.appendChild(resultsLogHeader);
            functionContainer.appendChild(functionResults);

            this.functionContainer = functionContainer;
            this.toolContainer.appendChild(functionContainer);

            this.scrollToBottom();


        // set function args height
        } else if (function_args != null){
            content = `${function_args}`;

            var existingText = this.functionArgsEl.textContent;

            this.functionArgsEl.style.height = 'auto';
            this.functionArgsEl.style.height = this.functionArgsEl.scrollHeight + 'px';
            this.functionArgsEl.textContent = existingText + content;
            this.scrollToBottom();
            

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

        // function results container/ pre element should alreaddy exist,
        // created during function call delta start
        var resultsJson = document.getElementById(`result__${tool_call_id}`);
        
        // pretty printJson
        //var resultJsonContainer = document.createElement('pre');
        resultsJson.innerHTML = JSON.stringify(JSON.parse(function_result), null, 2 );

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

    let tabContainer = document.getElementById('tabWrapper');
    let pageContent = document.getElementById('pageWrapper');
    //

    //let toolTestContainer = document.getElementById('toolTestContainer');
    let inputContainer = document.getElementById('inputWrapper');
    let consoleOutput = document.getElementById('consoleWrapper');

    let tabContainerHeight = tabContainer.offsetHeight;
    let inputContainerHeight = inputContainer.offsetHeight;
    let consoleOutputHeight = consoleOutput.offsetHeight;

    let newOutputHeight = window.innerHeight - (tabContainerHeight + inputContainerHeight + consoleOutputHeight ) ;

    newOutputHeight = Math.max(5, newOutputHeight);

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

        setWindowHeight();

        //window.addEventListener('load', (event) => { })

        this.stateValues();
        this.createSql();
        
        // TODO
        // send initial setting, needs a slight execution delay
        setTimeout(() => {
            this.getSettings();
        }, 100);


    }; // end constructor


    /*
    * send setting from js to
    */
     send_setting_val(elements){

        const settingsList = [];

        elements.forEach(element => {

            const setting_args = {
                "input_type": element.type,
                "setting_id": element.id,
                "setting_name": element.name,
                "setting_class": element.className,
            }

            if (element.type == "checkbox"){
                setting_args["setting_val"] = element.checked;
            } else{
                setting_args["setting_val"] = element.value;
            };


            if (element.value == "None"){
                setting_args["setting_val"] = null;
            };
            
            //console.log(input.id, input.value );
            settingsList.push(setting_args);

        }); // end for each

        const args = {
            "function_name": "update_settings",
            "function_args": {settings_list: settingsList},
        };

        adsk.fusionSendData("function_call", JSON.stringify(args))
            .then((result) =>{ });
    };



    getSettings(){

        const settingInputs = document.querySelectorAll('.setting-input');

        var settingsList = [];

        settingInputs.forEach(input => {
            //console.log(input.id, input.value );
            settingsList.push(input);
            //this.send_setting_val(input);
        }); // end for each

        this.send_setting_val(settingsList);

    }


    /*
    * 
    */
    stateValues(){

        
        // set div height on window resize
        window.addEventListener("resize", (event) => {setWindowHeight()});

        const settingInputs = document.querySelectorAll('.setting-input');

        settingInputs.forEach(input => {
            console.log(input.id, input.value );
            input.addEventListener("change", (event) => this.send_setting_val([event.target]));

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
        });
        

        // checkbox input an associeated element to hide
        const displayToggleElements = [
            {id: "showRuns", toggleElement: ".response-container"},
            {id: "showSteps", toggleElement: ".tool-container"},
            {id: "showResults", toggleElement: ".function-results" },
        ];
        //
        // checkboxes that toggle element display visibility
        displayToggleElements.forEach(input => {
            console.log(input.id, input.toggleElement );

            // checkbox input
            const inputElement = document.getElementById(input.id);

            inputElement.addEventListener("change", (event) => {
                this.showHideElement(input.toggleElement, event.target.checked)
                setWindowHeight();
            });

        }); // end for each


        // submit prompt on ender
        this.promptTextArea.addEventListener('keydown', (event) => {
            if ((event.key === 'Enter') && (this.submitOnEnter == true)){
                event.preventDefault(); // Prevent the default action (form submission)
                //this.promptTextArea.value += '*'; // Add an asterisk to the input field
                this.thread.submitPrompt()
            } // end if

        });// end submit on enter 




    }; // end state values


    /*
    * show hide all elements in a class
    */
    showHideElement(elementSelector, vis){
        let elements = document.querySelectorAll(`${elementSelector}`);
        console.log(elements.length);

        elements.forEach(e => {
            if (vis == true) {
                e.style.display = "block"; 
            } else {
                e.style.display = "none"; 
            }
        }) // end for each
        }; // end showHideElement


         toggleSettings(){

            const button = document.getElementById("toggleSettings");
            this.toggleElement("#settingsContainer", button);
        };



        toggleElement(elementSelector, button){
            let elements = document.querySelectorAll(`${elementSelector}`);
            elements.forEach(element => { 
                if (element.style.display != "none") {
                    element.style.display = "none"; 
                    button.textContent = button.textContent.replace("Hide", "Show");
                } else {
                    element.style.display = "block"; 
                    button.textContent = button.textContent.replace("Show", "Hide");

                } // end if else

            });
            setWindowHeight();
        };



        /*
         * #TODO probably find better name
         * server interface functions
         * =================================
         */

        /*
         * playback API call/response
         */
         playback(){
            const args = {function_name: "playback" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ });
            this.outputContainer.innerHTML = "";
        };

         printResponseMessages(){
            const args = {function_name: "print_response_messages" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ });
            //this.outputContainer.innerHTML = "";
        };

         clearOutputs(){
            this.outputContainer.innerHTML = "";
        };

        reloadModules(){
            const args = {function_name: "reload_modules" };
            // include current checkbox settings
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ this.get_current_cb_val(); }); // end then
        }; // end reload modules

        resize(){
            const args = {function_name: "resize_palette" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ }); // end then
        };

        reconnect(){
            const args = {function_name: "connect" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ }); // end then
        }; // end reconnect

        reloadObjectDict(){
            const args = {function_name: "reload_object_dict" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ 
                    this.get_current_cb_val();
                }); // end then
        };


        reloadFusionIntf(){
            const args = {function_name: "reload_fusion_intf" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ 
                    this.get_current_cb_val();
                }); // end then
        };

        uploadTools() {
            const args = {function_name: "upload_tools" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ });
        } // end uploadTools

        uploadModelSettings() {
            this.getSettings();
            const args = {function_name: "upload_model_settings" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((result) =>{ });
        } // end uploadTools

        /*
         * list availible Models
         */
        getModels(){
            const args = {function_name: "get_models" };
            adsk.fusionSendData("function_call", JSON.stringify(args))
                .then((str_results) =>{ 
                    const results = JSON.parse(str_results);
                    const modelsList = document.getElementById("modelsList");
                    modelsList.innerHTML = "";
                    results.forEach(option => {
                        const newOption = document.createElement('option');
                        newOption.value = option;
                        newOption.text = option;
                        modelsList.add(newOption);
                    });// end foreach
                });
        };


    toggleHelp(){

        let elements = document.querySelectorAll(".help");

        const button = document.getElementById("toggleHelp");

        if (button.textContent.includes("Show") == true ) {
            button.textContent = button.textContent.replace("Show", "Hide");
        } else {

            button.textContent = button.textContent.replace("Hide", "Show");

        }


        elements.forEach(e => {

            const parentE = e.parentElement;

            if ((e.style.display == "") |(e.style.display == "none"))  {
                e.style.display = "block"; 
                parentE.style.borderWidth = "1px";
                parentE.style.padding = "5px";
                parentE.style.borderRadius = "5px";
                parentE.style.borderColor = "red";
                parentE.style.borderStyle = "solid";
                //parentE.style.display = "block";

            } else {
                e.style.display = "none"; 
                parentE.style.border = ""; 
                parentE.style.padding = "1px";
                //parentE.style.display = "flex";

            }

        }) // end for each

        setWindowHeight();
    }



    /*
     * list availible Models
     */
    getInstructions(){
        const args = {function_name: "get_system_instructions"};
        adsk.fusionSendData("function_call", JSON.stringify(args))
            .then((str_results) =>{ 
                const results = JSON.parse(str_results);
                const instructionsList = document.getElementById("instructionsList");
                instructionsList.innerHTML = "SketchPoint";
                results.forEach(option => {
                    const newOption = document.createElement('option');
                    newOption.value = option;
                    newOption.text = option;
                    instructionsList.add(newOption);
                });// end foreach
            });
    };


    resetAll(){
        const args = { };
        this.outputContainer.innerHTML = ""
        this.toolTestContainer.innerHTML = ""
        adsk.fusionSendData("reset_all", JSON.stringify(args))
            .then((result) =>{ }); // end then
    };


    record(){

        let recordButton = document.getElementById('recordButton');
        recordButton.style.backgroundColor = "gray";

        if ( recordButton.textContent == "Start Record"){
            const args = {function_name: "start_record" };
            adsk.fusionSendData("call_function", JSON.stringify(args)).then((result) =>{ 
                recordButton.style.backgroundColor = "red";
                recordButton.textContent = "Recording";
            });


        } else {

            recordButton.textContent = "Transcribing...";
            const args = {function_name: "stop_record" };
            // Send the data to Fusion as a JSON string. The return value is a Promise.
            adsk.fusionSendData("call_function", JSON.stringify(args))
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

     async toggleTools() {

         if (this.tools.length == 0){
            this.tools = await this.getTools();
            this.createToolElements();
        };

    } // end hide tools


    /*
     * change tab
     */
    changeTab(tabIndex){

        let tabs  = document.querySelectorAll(".content-tab");
        let tabButtons = document.querySelectorAll(".tab-button");

        for (let i=0; i < tabs.length; i++) {

            let element = tabs[i];
            let buttonElement = tabButtons[i];

            if (i == tabIndex) {
                element.style.display = "block"; 
                buttonElement.style.backgroundColor = "#1B1212"; 
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




    /*
    * get availible tool call from Python class
    */
     async getTools() {

         const args = {function_name: "get_tools"};
         var result = await adsk.fusionSendData("function_call", JSON.stringify(args));
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

    execute_sql(textArea){

        const queryString  = textArea.value.trim();

        const args = {"function_name": "run_sql_query", "function_args": {"query_str": queryString} };

        adsk.fusionSendData("execute_tool_call", JSON.stringify(args))
        .then((result) =>{ }); // end then


    } // end execute sql
     countChar(str, char) {
      let count = 0;
      for (let i = 0; i < str.length; i++) {
        if (str[i] === char) {
          count++;
        }
      }
      return count;
    }

    createSql(){
        //console.log(queryStrings);
        //querysContainer defined in seperate file
        let querysContainer = document.getElementById('sqlContent');

        queryStrings.forEach(query => {

            const qContainer = document.createElement("div");
            qContainer.className = "sql-row";
            const qText = document.createElement("textarea");
            qText.className = "sql";
            query =  query.replace("FROM", "\nFROM").replace("SET", "\nSET").replace("WHERE", "\nWHERE")
            query =  query.replace("LIMIT", "\nLIMIT")

            query =  query.replace("\n\n", "\n")

            qText.innerHTML = query.trim();

            let n_breaks = this.countChar(query, "\n");
            //console.log(n_breaks);

            qText.style.height = 35 + (35 * n_breaks) +"px"; // Reset the height

            const qButton = document.createElement("button");
            qButton.innerHTML = "run";

            qButton.onclick = (event) =>{
                this.execute_sql(qText);

            };

            qContainer.appendChild(qText);
            qContainer.appendChild(qButton);
            querysContainer.appendChild(qContainer);

            //
            //console.log(qText.scrollHeight );
            //qText.style.height = qText.scrollHeight + "px"; // Set height to scroll height


        });




    }


    createToolElements() {
        let toolTestContainer = document.getElementById('toolTestContainer');
        toolTestContainer.innerHTML = "";

        for (const [c_name, methods] of Object.entries(this.tools)) {

            // methods
            // top class container
            const toolClassContainer = document.createElement("div");
            toolClassContainer.className = "toolClassContainer";

            //const classSectionTitle = document.createElement("span");
            const classSectionTitle = document.createElement("button");
            classSectionTitle.innerHTML = c_name;
            classSectionTitle.type = "button";
            classSectionTitle.className = "tool-call-class-title";

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
                functionButton.className = "tool-call-button";

                const inputContainer = document.createElement("span");
                inputContainer.className = "function-input-container";

                // params
                for (const [param_name, param_info] of Object.entries(params)) {
                    //const paramInput = document.createElement("input");
                    const paramInput = document.createElement("textarea");
                    //console.log(param_name,param_info);
                    const paramType = param_info.type

                    let paramColor = "none";
                    if (paramType == "str"){
                        paramColor = "#FFEBDD";

                    } else if (paramType == "float"){
                        paramColor = "#FEF7E8";

                    } else if (paramType == "list"){
                        paramColor = "#FED7FB";
                    } else if (paramType == "dict"){
                        paramColor = "#E3FEF7";

                    };

                    paramInput.style.backgroundColor=paramColor;

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


                    //paramInput.addEventListener("click", () => autoResizeTextarea(paramInput));

                    inputContainer.appendChild(paramInput);
                    autoResizeTextarea(paramInput);
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


    resizeInput(input) {
        input.style.width = (5 +input.value.length) + "ch"; // Adjust multiplier for better spacing

    } // end resize


} // end control container








let thread;
let control;

//document.addEventListener("DOMContentLoaded", (event) => {
//
//    thread = new Thread();
//    control = new Control(thread);
//
//});

function connectionError(){
    promptTextArea = document.getElementById('promptTextInput');
    promptTextArea.textContent = "ERROR: MAKE SURE 'connection.py' IS RUNNING";
};



window.addEventListener('load', (event) => { 
    thread = new Thread();
    control = new Control(thread);

});// end window on load

// reload css for debugging
function reloadStyle() {
    console.log("reload style");

  const links = document.querySelectorAll('link[rel="stylesheet"]');
  links.forEach(link => {
    const href = link.href;
    const newHref = href.includes('?') ? `${href}&reload=${Date.now()}` : `${href}?reload=${Date.now()}`;
    link.href = newHref;
  });
}




window.fusionJavaScriptHandler = {

    handle: function (action, messageString) {

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
                console.log(messageData);
                thread.toolCallResponse(messageData);

            } else if (action === "get_initial") {
                control.getSettings();

            } else if (action === "connection_error") {
                connectionError();

            // TODO print all errors to browser console
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













