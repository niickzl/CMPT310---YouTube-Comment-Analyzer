# CMPT310

**FOR TESTERS:**

**Connect to Google**

Open Chrome -> go to ```chrome://extensions/``` -> 

toggle developer mode "ON" -> Click on "Load unpacked" -> 

Select the local `extension` folder.


**Loadup Backend**

Open Terminal in the local file directory and type:

```cd backend```

```uvicorn main:app --reload```

---

**FOR MODERATORS:**

Run ```python -m venv .venv``` in terminal.

Then run 

(RUN THIS EVERYTIME YOU WORK ON THIS)

```.venv/Scripts/activate``` (Windows)

```source .venv/bin/active``` (Mac/Linux)

Then run ```pip install fastapi uvicorn spacy scikit-learn torch transformers```

Then run ```python -m spacy download en_core_web_sm```