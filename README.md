

Fusion 360 - OpenaAI Assistants API Add-In


# file structure

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
│   ├── fusion_config.env
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
├── gpt_config.env
├── oai_container
│   ├── connection.py
│   ├── system_instructions.txt
│   ├── test_client.py
│   └── tools.json
└── requirements.txt




Fusion-GPT-Addin
    This is the actual Add-In, must be loaded into Fusion 360


oai_container
    relating to OpenAI Assistants api
    connection.py is run in a separate process, the Fusion 360 Add-In Connects during runtime















