
Fusion 360 - OpenaAI Assistants API Add-In


# file structure

`
├── Fusion-GPT-Addin
│   ├── GptAddin.manifest
│   ├── GptAddin.py
│   ├── commands
│   │   ├── Browser
│   │   │   ├── __init__.py
│   │   │   ├── entry.py
│   │   │   └── resources
│   │   └── __init__.py
│   ├── config.py
│   └── lib
│       ├── fusion360utils
│       │   ├── __init__.py
│       │   ├── event_utils.py
│       │   └── general_utils.py
│       └── sutil
│           ├── __init__.py
│           └── fusion_interface.py
├── README.md
├── fusion_env
├── config.env
├── oai_container
│   ├── connection.py
│   ├── system_instructions.txt
│   ├── test_client.py
│   └── tools.json
└── requirements.txt
`

# Structure
"Fusion-GPT-Addin" This is the actual Add-In, must be loaded into Fusion 360

"oai_container" contains the code relating to the Assistants API. "connection.py" is run in a separate process than Fusion. The Fusion 360 Add-In connects during run time.


# Setup
    1.  Create an OpenAI Assistant at https://platform.openai.com/assistants/
    2.  Rename the config.sample to config.env, add your OpenAI API key
        and AssistantID
    3.  Create a virtual Python environment for this project
    4.  Install required libraries from the requirements.txt file

# Run
    1. In Fusion 360 navigate to the utilities tab
    2. In the Add-Ins section, click on the green + icon and load the
       directory "Fusion-GPT-Addin"
    3. Click run, to run the Add-In




















