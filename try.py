from fastapi import FastAPI

app = FastAPI()

@app.get("/", response_model=dict)
def read_root():
    return {"Hello": "Working"}
