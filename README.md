
# Overview
Fusion 360 - OpenaAI Assistants API Add-In.
This Fusion 360 Python Add-In allows the OpenAI Assistant API to interact with the design workspace.

# Key Points
    1. Fusion 360 runs the python Add-Ins (e.g. "Fusion-GPT-Addin") in the built in Fusion 360 Python environment. It is relatively difficult and not recommended to modify (install third party packages) the built in Fusion 360 Python environment.
    2. To overcome the limitations of the Fusion 360 environment, we run a separate Python program with its own environment, on a separate process. This program is located in the directory "oai_container".
    3. The two Python programs communicate with each other via the Python "multiprocessing" package.





# Structure
```
├── Fusion-GPT-Addin
│   ├── GptAddin.manifest
│   ├── GptAddin.py
│   ├── commands
│   │   └── Browser
│   │       ├── entry.py
│   │       └── resources
│   │           ├── 16x16.png
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

1. "Fusion-GPT-Addin" is the actual Fusion 360 Add-In, must be loaded into Fusion 360 via the utilities tab
2. "oai_container" contains the code relating to the Assistants API. "connection.py" is run in a separate process than Fusion. The Fusion 360 Add-In connects during run time
3. "Browser" directory contains files for the HTML window displayed in Fusion

# Setup
    1.  Create an OpenAI Assistant at https://platform.openai.com/assistants/
        Currently, you must have paid credits on the OpenAI Developer API.
    2.  Rename the config.sample to config.env, add your OpenAI API key and AssistantID
    3.  Create a virtual Python environment for this project
    4.  Install required libraries from the requirements.txt file

# Run
    1. In Fusion 360 navigate to the utilities tab
    2. In the Add-Ins section, click on the green + icon and load the directory "Fusion-GPT-Addin"
    3. Click run, to run the Add-In
















