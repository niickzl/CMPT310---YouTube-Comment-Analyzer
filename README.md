# CMPT310

**FOR TESTERS:**

Open Chrome -> go to ```chrome://extensions/``` -> 

toggle developer mode "ON" -> Click on "Load unpacked" -> 

Select the local `extension` folder.


Open Terminal in the local file directory and type:
```cd backend```
```uvicorn main:app --reload```

---

**FOR MODERATORS:**

Run ```python -m venv .venv``` in terminal.

(RUN THIS EVERYTIME YOU WORK ON THIS)
Then run 

```.venv/Scripts/activate``` (Windows)

```source .venv/bin/active``` (Mac/Linux)

Then run ```pip install fastapi uvicorn spacy scikit-learn torch transformers```

Then run ```python -m spacy download en_core_web_sm```