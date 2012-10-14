from flask import Flask, render_template, request, redirect, url_for, abort, session
import boto
import MySQLdb

app = Flask('picturedb')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'

@app.route('/image/<img_id>', )
def get_image(img_id):
    