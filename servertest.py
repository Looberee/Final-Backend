from flask import Flask, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.route('/')
def index():
    # Set a value in the session
    session['test_key'] = 'test_value'
    return 'Session value set'

@app.route('/retrieve')
def retrieve_session():
    session_value = session.get('test_key')
    return session_value or 'Session value not found'

@app.route('/clear')
def clear():
    # Clear the session
    session.clear()
    return 'Session cleared'

if __name__ == '__main__':
    app.run(debug=True)
