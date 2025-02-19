
# Overview
### Fusion 360 - OpenaAI Assistants API Add-In.
### This Fusion 360 Python Add-In allows the OpenAI Assistant API to interact with the design workspace.

## Key Points
    1. Fusion 360 runs Python Add-Ins (e.g. "Fusion-GPT-Addin") in the built in Fusion 360 Python environment. It is relatively difficult and not recommended to modify (install third party packages) the built in Fusion 360 Python environment.
    2. To overcome this limitation, we run a separate Python program with its own environment, on a separate process. This program is called "connection.py" located in the directory "oai_container".
    3. The two Python programs communicate with each other via the Python "multiprocessing" package.
    4. When running the Add-In, please open the Fusion 360 Text Commands window. This provides details on errors and other runtime messages.


# Set Up

## setup Overview
    1. "Fusion-GPT-Addin" is the actual Fusion 360 Add-In, must be loaded into Fusion 360 via the utilities tab
    2. "oai_container" contains the code relating to the Assistants API. "connection.py" is run in a separate process than Fusion. The Fusion 360 Add-In connects during run time
    3. "Browser" directory contains files for the HTML window displayed in Fusion

## Config / Environment Setup
    1.  Create an OpenAI Assistant at https://platform.openai.com/assistants/ Currently, you must have paid credits on the OpenAI Developer API. 
    2.  Rename the "config.sample" to "config.env", add your OpenAI API key and AssistantID, which you will find in the OpenAI Assistant Dashboard.
    3. I used Python 3.11 for this project. While it's not required, I highly recommend setting up a virtual environment. Create a virtual Python environment for this project.  If you are unfamiliar with setting up a downloading Python/ setting up a virtual environment, google/chatgpt "How to install Python and create a virtual environment" 
    4.  Install required libraries from the requirements.txt file

## Add-In setup
    1. In Fusion 360 navigate to the utilities tab
    2. In the Add-Ins section, click on the green + icon and load the directory "Fusion-GPT-Addin"
    3. Click run, to run the Add-In.
    4. Now in the utilities tab you should see a new icon called Fusion-GPT-Addin
    5. Click on the icon to open the prompt window

    4. Please open the Fusion 360 Text Commands window. If the Add-In is not working properly, you should check the output here first.



# Usage
## Assistants API Connection
    1. If you are using a virtual environment, activate it now.
    2. Navigate to "<project_root>/oai_container/" and run "connection.py" (python connection.py)
    3. In the console you should see "WAITING FOR FUSION 360 TO CONNECT"

## Assistant Config
    1. Click on the Add-Icon in the utilities tab, the prompt window should appear.
    2. Click on the "Settings" checkbox to expand all settings. 
    3. We need to set up the Assistant's, System Instructions, Model, Tool (functions). S



# Structure
```
├── Fusion-GPT-Addin
│   ├── GptAddin.manifest
│   ├── GptAddin.py
│   ├── commands
│   │   └── Browser
│   │       ├── entry.py
│   │       └── resources
│   │           ├── 16x16.pngo
│   │           ├── 32x32.png 
│   │           ├── 64x64.png
│   │           └── html
│   │               ├── index.html
│   │               └── static
│   │                   ├── palette.js
│   │                   └── style.css
│   ├── config.py
│   └── f_interface
│       ├── fusion_interface.py
│       ├── gpt_client.py
│       └── modules
│           ├── cad_modeling.py
│           ├── document_data.py
│           ├── shared.py
│           ├── transient_objects.py
│           └── utilities.py
├── README.md
├── config.sample
├── oai_container
│   ├── connection.py
│   ├── fusion_types.py
│   ├── system_instructions.txt
│   ├── system_instructions_v1.txt
│   └── test_client.py
├── requirements.txt
└── sample_prompts.txt
```

















