
# Overview
Fusion 360 - OpenaAI Assistants API Add-In.
This Fusion 360 Python Add-In allows the OpenAI Assistant API to interact with the design workspace.


# Structure
```
├── Fusion-GPT-Addin
│   ├── GptAddin.manifest
│   ├── GptAddin.py
│   ├── commands
│   │   ├── Browser
│   │   │   ├── __init__.py
│   │   │   ├── entry.py
│   │   │   └── resources
│   │   │       ├── 16x16.png
│   │   │       ├── 32x32.png
│   │   │       ├── 64x64.png
│   │   │       └── html
│   │   │           ├── index.html
│   │   │           └── static
│   │   └── __init__.py
│   ├── config.py
│   └── lib
│       ├── fusion360utils
│       │   ├── __init__.py
│       │   ├── event_utils.py
│       │   └── general_utils.py
│       └── sutil
│           ├── __init__.py
│           ├── fusion_interface.py
│           └── gpt_client.py
├── README.md
├── config.env
├── config.sample
├── fusion_env
├── oai_container
│   ├── connection.py
│   ├── system_instructions.txt
│   └── test_client.py
├── requirements.txt
└── sample_prompts.txt
```

1. "Fusion-GPT-Addin" is the actual Fusion 360 Add-In, must be loaded into Fusion 360 via the utilities tab
2. "oai_container" contains the code relating to the Assistants API. "connection.py" is run in a separate process than Fusion. The Fusion 360 Add-In connects during run time
3. "Browser" directory contains files for the HTML window displayed in Fusion

# Setup
    1.  Create an OpenAI Assistant at https://platform.openai.com/assistants/
    2.  Rename the config.sample to config.env, add your OpenAI API key and AssistantID
    3.  Create a virtual Python environment for this project
    4.  Install required libraries from the requirements.txt file

# Run
    1. In Fusion 360 navigate to the utilities tab
    2. In the Add-Ins section, click on the green + icon and load the directory "Fusion-GPT-Addin"
    3. Click run, to run the Add-In


# Bugs
payments
new design

















