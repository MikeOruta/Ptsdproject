"""Start the development server:  python run.py  then open http://127.0.0.1:5000"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True reloads on code changes and shows errors. Development only.
    app.run(debug=True)
