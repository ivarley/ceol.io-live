from flask import Flask, render_template
import random
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!!'

@app.route('/magic')
def magic():
    magic_number = random.randint(1, 8)
    return render_template('magic.html', number=magic_number)
