from backend.movie_api import fetch_movies, search_movies, fetch_discover_movies, fetch_movie_details
from flask import Blueprint, request, render_template, flash,  session, url_for, redirect, Flask, jsonify
from backend.database import db
from backend.tv_show_api import get_popular_tv_shows_for_carousel
from backend.music_api import get_home_tracks, get_search_tracks, get_track_info
from backend.search_form import SearchForm
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import User, Comment


main = Blueprint('main', __name__)

@main.route('/')
def home():
    movies = fetch_movies()
    if not movies:
        return "Failed to fetch movies. Please try again later.", 500
    tracks = get_home_tracks()
    shows = get_popular_tv_shows_for_carousel()
    return render_template('home.html', movies=movies, tracks=tracks, shows=shows)


@main.route('/movies', methods=['GET'])
def movies_search():
    query = request.args.get('q', '')
    if query:
        movies = search_movies(query)
    else:
        movies = fetch_discover_movies()
    
    return render_template('movies_search.html', movies=movies, search_query=query)

@main.route('/movie/<int:movie_id>')
def movie(movie_id):
    movie = fetch_movie_details(movie_id=movie_id)
    if 'status_code' in movie and movie['status_code'] == 34:
        return redirect(url_for('main.movies_search'))
    
    return render_template('movie.html', movie=movie)

@main.route('/submit_review/<int:movie_id>', methods=['POST'])
def submit_review(movie_id):
    rating = request.form.get('rating')
    # Process the rating (e.g., save it to the database)
    flash('Thank you for your review!', 'success')
    return redirect(url_for('main.movie', movie_id=movie_id))

from flask import request, jsonify

@main.route('/comments', methods=['GET'])
def get_comments():
    movie_id = request.args.get('movie_id')
    timestamp = int(request.args.get('timestamp', 0))
    comments = Comment.query.filter_by(movie_id=movie_id, timestamp=timestamp).all()
    comments_data = [{'timestamp': c.timestamp, 'text': c.text} for c in comments]
    return jsonify(comments_data)

@main.route('/submit_comment', methods=['POST'])
def submit_comment():
    data = request.get_json()
    movie_id = data['movie_id']
    text = data['text']
    timestamp = data['timestamp']
    new_comment = Comment(movie_id=movie_id, text=text, timestamp=timestamp)
    db.session.add(new_comment)
    db.session.commit()
    return jsonify({'success': True})





@main.route('/music')
@main.route('/music', methods=['GET','POST'])
def music_search():
    form = SearchForm()
    results = []

    if form.validate_on_submit():
        results = get_search_tracks( form.name_search.data )
        print("$####################")
        print(results[0])
        
    return render_template('music_search.html', results=results, form=form)

@main.route('/temp')
def temp():
    id = request.args.get('id', None)
    if id:
        song_info = get_track_info(id)
    else:
        song_id = None
    return render_template('temp.html', song_info=song_info)

@main.route('/song/<song_id>')
def song_detail(song_id):
    # Retrieve song details, comments, and other relevant data from the database
    song = get_track_info(song_id) #db.get_song_by_id(song_id)
    #comments = db.get_comments_for_song(song_id)

    # this is a placeholder for now, until we design the db 
    comments = [{'username': 'egger',
                 'text': 'when he said "so many racks they call me the bandman" i felt that',
                 'timestamp': '5:55'
                },
                {'username': 'second user',
                 'text': 'wowzers',
                 'timestamp': '1:01'
                }]
    print(song['artists'])
    return render_template('song.html', song=song, comments=comments)

@main.route('/shows')
def shows_search():
    return render_template('shows_search.html')




# @main.route('/music_search', methods=['GET'])
# def music_search():
#     query = request.args.get('q', '')
#     results = search_songs(query)  # Replace with your actual search function
#     return render_template('music_search_results.html', query=query)

# @main.route('/song/<int:song_id>')
# def song_detail(song_id):
#     # Retrieve song details, comments, and other relevant data from the database
#     song = db.get_song_by_id(song_id)
#     comments = db.get_comments_for_song(song_id)
#     return render_template('song_detail.html', song=song, comments=comments)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            new_user = User(username=username, password=generate_password_hash(password), email=email)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('main.login'))

    return render_template('register.html')

# @main.route('/dashboard')
# def dashboard():
#     if 'username' not in session:
#         flash('Please login to access this page', 'danger')
#         return redirect(url_for('login'))

#     return f'Welcome to your dashboard, {session["username"]}!'

@main.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('main.login'))
