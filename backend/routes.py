from backend.movie_api import fetch_movies, search_movies, fetch_discover_movies, fetch_movie_details
import flask
from flask import Blueprint, request, render_template, flash,  session, url_for, redirect, Flask, jsonify
from backend.database import db
from backend.tv_show_api import get_popular_tv_shows_for_carousel
from backend.music_api import get_home_tracks, get_search_tracks, get_track_info
from backend.search_form import SearchForm
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import User, Comment, Rating, Media
from backend.tv_show_api import get_popular_tv_shows_for_carousel, get_tv_show_details, fetch_show_details, fetch_episode_details, search_tv_shows, get_popular_tv_shows, fetch_season_episodes, fetch_show_poster, fetch_shows
from datetime import timedelta
import requests
import json
import datetime

from backend.spotify_authentication import create_spotify_login_link, callback_result, token_refresh_result, get_current_track_info, put_pause_and_play

USER_ID = False

main = Blueprint('main', __name__)



@main.route('/')
def home():
    global USER_ID

    if 'user_id' in session:
        USER_ID = session['user_id']
        print(True)
    else:
        USER_ID = None
        print(False)

    movies = fetch_movies()
    tracks = get_home_tracks()
    shows = fetch_shows()
    return render_template('home.html', movies=movies, tracks=tracks, shows=shows)

######################################
##########SPOTIFY LOGIN###############
######################################
@main.route('/spotify_login')
def spotify_login():

    spotify_login_link_url = create_spotify_login_link(show_dialog=request.args.get('show_dialog'))
    return redirect(spotify_login_link_url)

@main.route('/callback')
def callback(): # this will handle both successful and unsuccessful login attempts
    global USER_ID
    ### for some reason, the deletes the session when it reaches this route ###
    ## i ended up redifining the entire session in the "callback_result" function

    callback_successful = callback_result(request=request, session=session, user_id_var=USER_ID)

    if callback_successful:
        return redirect(url_for('main.music_search', came_from_callback=True))
        #user.spotify_access_token = token_info['access_token']  # used to do tasks requiring auth (lasts a day)
        #user.spotify_refresh_token = token_info['refresh_token']  # used to avoid user needing to login after token expires
        #user.spotify_expires_at = datetime.now().timestamp() + token_info['expires_in']  # used to avoid user needing to login after token expires
    else:
        return {'error': request.args['error']}
                    
######################################
##########SPOTIFY LOGIN###############
######################################


@main.route('/music', methods=['GET', 'POST'])
def music_search():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))


    print("MADE IT BACK TO MUSIC Search")
    came_from_callback = request.args.get('came_from_callback', None)
    if came_from_callback:
        global USER_ID
        USER_ID = session['user_id']
        user = db.session.query(User).filter(User.id == session['user_id']).first()
        user.spotify_access_token = session['spotify_access_token']  # used to do tasks requiring auth (lasts a day)
        user.spotify_refresh_token = session['spotify_refresh_token']  # used to avoid user needing to login after token expires
        user.spotify_expires_at = session['spotify_expires_at']  # used to avoid user needing to login after token expires
        db.session.commit()
        print(user.id)
        print(user.spotify_access_token)
        print(user.spotify_refresh_token)
        print(user.spotify_expires_at)

    user_signed_in_to_chatter = 'user_id' in session
    user_id = session['user_id']
    user_signed_in_to_spotify = None

    if user_signed_in_to_chatter:
        user = db.session.query(User).filter(User.id == session['user_id']).first()
        user_signed_in_to_spotify = user.spotify_access_token  != None
        
    form = SearchForm()
    results = []

    if form.validate_on_submit():
        results = get_search_tracks(form.name_search.data)
        # i made it so that if there are no tracks for the search, the following will be returned: [False]
        if len(results) == 1 and results[0] == False:
            results = 'Result Not Found'
        search_query = form.name_search.data
    else:
        results = get_home_tracks()
        search_query = None
        
    return render_template('music_search.html', results=results, form=form, search_query=search_query, user_signed_in_to_chatter=user_signed_in_to_chatter, user_signed_in_to_spotify=user_signed_in_to_spotify, user_id=user_id)

@main.route('/song/<song_id>')
def song_detail(song_id):
    # Retrieve song details, comments, and other relevant data from the database
    song = get_track_info(song_id) #db.get_song_by_id(song_id)
    print(song['artists'])
    return render_template('song.html', song=song)


@main.route('/music_player')      
def music_player():
    user = db.session.query(User).filter(User.id == session['user_id']).first()

    print('got to get_live_player screen')


    if user.spotify_access_token == None:
        return redirect(url_for('spotify_login', show_dialog=False))
    print(f"what is currently on db {datetime.datetime.now().timestamp()}")
    print(f"current time {user.spotify_expires_at}")
    print(f' token expires AFTER current time:{datetime.datetime.now().timestamp() > user.spotify_expires_at}')

    # if token is expired, we will refresh it in the background (user will not need to login again)
    if datetime.datetime.now().timestamp() > float(user.spotify_expires_at):
        print('token expired, refreshing.......')
        return redirect(url_for('main.spotify_refresh_token'))


    session['spotify_access_token'] = user.spotify_access_token
    session['spotify_expires_at'] = user.spotify_expires_at
    access_token = user.spotify_access_token
    currently_playing_response = get_current_track_info(access_token)
    #print(currently_playing_response)
    #print(currently_playing_response.json())

    playback_status_return = {}

    if currently_playing_response.status_code == 204:
        flash("there is no media currently playing")
        print("there is no media currently playing")
    elif currently_playing_response.status_code == 200:
        playback_status = currently_playing_response.json()
        if playback_status['item'] != None:
            playback_status_return['image'] = playback_status['item']['album']['images'][1]['url']
            playback_status_return['name'] = playback_status['item']['name']
            playback_status_return['id'] = playback_status['item']['id']
            playback_status_return['duration_ms'] = playback_status['item']['duration_ms']
            playback_status_return['progress_ms'] = playback_status['progress_ms']
        else:
            playback_status = {'good response, but empty item'}
    else: 
        playback_status_return = {'there was a bad status code on playback status'}

    return render_template('music_player.html', playback_status=playback_status_return)

@main.route('/get_live_player_info', methods=['GET', 'POST'])
def get_live_player_info():

    # set spotify_access_token and spotify_expires_at

    # "access_token" will only be in session if user is logged in
    if 'spotify_access_token' not in session:
        user = db.session.query(User).filter(User.id == session['user_id']).first()
        session['spotify_access_token'] = user.spotify_access_token
    if 'spotify_expires_at' not in session:
        user = db.session.query(User).filter(User.id == session['user_id']).first()
        session['spotify_expires_at'] = user.spotify_expires_at


    spotify_access_token = session['spotify_access_token']
    spotify_expires_at = session['spotify_expires_at']

    # force user to login if not logged in
    if spotify_access_token == None:
        return redirect(url_for('spotify_login', show_dialog=False))

    # if token is expired, we will refresh it in the background (user will not need to login again)
    if datetime.datetime.now().timestamp() > spotify_expires_at:
        print('token expired, refreshing.......')
        return redirect(url_for('main. spotify_refresh_token'))

    # makes rrequest to spotify api
    currently_playing_response = get_current_track_info(spotify_access_token)
    if currently_playing_response.status_code == 200:
        return jsonify(currently_playing_response.json())
    if currently_playing_response.status_code == 204:
        return jsonify({})
    else:
        return jsonify({0})

@main.route('/pause_and_play', methods=['GET', 'POST'])
def pause_and_play():
    device_id = request.args.get('device_id', None)
    spotify_access_token = session['spotify_access_token']

    print(device_id)
    if device_id:
        pause_and_play_response = put_pause_and_play(spotify_access_token=spotify_access_token, device_id=device_id)
        print(pause_and_play_response)
        print(pause_and_play_response.json())
        return pause_and_play_response.json()
    else:
        print('no user id was passed')

@main.route('/spotify_refresh_token')
def spotify_refresh_token():
    user = db.session.query(User).filter(User.id == session['user_id']).first()

    if user.spotify_refresh_token == None:
        return redirect(url_for('spotify_login', show_dialog=False))
    
    response = token_refresh_result(user.spotify_refresh_token)
    new_token_info = response.json()

    # REPLACE TO DATABSE CALL
    user.spotify_access_token = new_token_info['access_token']  # used to do tasks requiring auth (lasts a day)
    user.spotify_expires_at = datetime.datetime.now().timestamp() + new_token_info['expires_in']  # keeping track of when token expires
    db.session.commit()
    session['spotify_access_token'] = user.spotify_access_token
    session['spotify_expires_at'] = user.spotify_expires_at

    print(f'REAL NEW EXPIRES AT:{ datetime.datetime.now().timestamp() + new_token_info["expires_in"]}')

    return redirect(url_for('main.music_search'))













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

@main.route('/submit_review', methods=['POST'])
def submit_review():    

    # define variables from url params
    media_title  = request.args.get('media_title', None)
    media_id = request.args.get('media_id', None)
    media_type  = request.args.get('media_type', None)

     # check if user is signed in
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # obtain neccesary vars from session and form 
    user_id = session['user_id']
    rating_given = request.form.get('rating')

    # define user and media var (note, if media is not found, it will default to NONE)
    user = db.session.query(User).filter(User.id == user_id).first()
    media = db.session.query(Media).filter(Media.id == media_id).first()
    rating = db.session.query(Rating).join(Media).filter(Rating.user_id == user_id, Media.id == media_id).first()

    # create a media object if none is found
    if not media:
        media = Media(id=media_id, title=media_title, media_type=media_type)
        db.session.add(media)
        db.session.commit()

    # add rating if not present, and update if alr presnet
    if user and media:
        if not rating:
            new_rating = Rating(user_id=user.id, media_id=media.unique_id, rating=rating_given)
            db.session.add(new_rating)
            print("CREATED NEW RATING")
        if rating:
            rating.rating = rating_given
            print("UPDATED RATING")
        db.session.commit()

    if media_type == 'movie':
        return redirect(url_for('main.movie', movie_id=media_id))
    if media_type == 'music':
        return redirect(url_for('main.song_detail', song_id=media_id))
    if media_type == 'show':
        return redirect(url_for('main.episode_details', episode_id=media_id))
    else:
        # Handle other media types (if applicable)
        return redirect(url_for('main.index'))
    
    # Process the rating (e.g., save it to the database)
    #flash('Thank you for your review!', 'success')
    #return redirect(url_for('main.movie', movie_id=movie_id))

@main.route('/submit_review_show', methods=['POST'])
def submit_review_show():

    # define variables from url params
    media_title  = request.args.get('media_title', None)
    media_id = request.args.get('media_id', None)
    print(media_id)
    media_type  = request.args.get('media_type', None)
    episode_title = request.args.get('episode_title', None)
    season_number=request.args.get('season_number', None) 
    episode_number=request.args.get('episode_number', None)

    # obtain neccesary vars from session and form 
    user_id = session['user_id']
    rating_given = request.form.get('rating')

    print(f'userid = {user_id}')

    # check if user is signed in
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    episode = db.session.query(Media).filter(Media.id == media_id, Media.season_number == season_number, Media.episode_number == episode_number).first()
    print(episode)
    rating = db.session.query(Rating).join(Media).filter(Rating.user_id == user_id, Media.id == media_id, Rating.season_number == season_number, Rating.episode_number == episode_number).first()
    print(rating)

    #  # create a media object if none is found
    # if not media:
    #     media = Media(id=media_id, title=media_title, media_type=media_type)
 
    # if current episode doesnt exist, add it to 
    if not episode:
        episode = Media(id=media_id, title=media_title, media_type=media_type, season_number=season_number, episode_number=episode_number, episode_title=episode_title)
        db.session.add(episode)
        db.session.commit()
    
    
    # add rating if not present, and update if alr presnet
    if not rating:
        new_rating = Rating(user_id=user_id, media_id=episode.unique_id, rating=rating_given, season_number=season_number, episode_number=episode_number )
        db.session.add(new_rating)
        print("CREATED NEW RATING")
    if rating:
        rating.rating = rating_given
        print("UPDATED RATING")
    db.session.commit()

    return redirect(url_for('main.episode_details', show_id=int(media_id), season_number=season_number, episode_number=episode_number))


@main.route('/submit_comment_show', methods=['POST'])
def submit_comment_show():

    # define variables from url params
    media_title  = request.args.get('media_title', None)
    media_id = request.args.get('media_id', None) # id of the show
    media_type  = request.args.get('media_type', None)
    episode_title = request.args.get('episode_title', None)
    season_number=request.args.get('season_number', None) 
    episode_number=request.args.get('episode_number', None)

    # obtain neccesary vars from session and form 
    user_id = session['user_id']
    timestamp = request.form.get('timestamp')
    text = request.form.get('text')

    # check if user is signed in
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    episode = db.session.query(Media).filter(Comment.user_id == user_id, Media.id == media_id, Media.episode_number == int(episode_number), Media.season_number == int(season_number)).first()
    print(episode)
    #comment = db.session.query(Comment).filter(Comment.user_id == user_id, Rating.media_id == media_id, Rating.season_number == season_number, Rating.episode_number == episode_number).first()

    #  # create a media object if none is found
    # if not media:
    #     media = Media(id=media_id, title=media_title, media_type=media_type)
 
    # if current episode doesnt exist, add it to 
    if not episode:
        episode = Media(id=media_id, title=media_title, media_type=media_type, season_number=int(season_number), episode_number=int(episode_number), episode_title=episode_title)
        db.session.add(episode)
        db.session.commit()

    print("faoejfoajeofjaefjaeof")
    print(timestamp)
    #print(episode.unique_id)
    #print(episode.title)
    print(episode.id)
    #print(episode.media_type)
    print(episode.season_number)
    print(episode.episode_number)
    #print(episode.episode_title)

    # add rating if not present, and update if alr presnet
    new_comment = Comment(user_id=user_id, media_id=episode.unique_id, timestamp=int(timestamp), text=text, season_number=season_number, episode_number=episode_number )
    db.session.add(new_comment)
    db.session.commit()


    return redirect(url_for('main.episode_details', show_id=int(media_id), season_number=season_number, episode_number=episode_number))

@main.route('/shows', methods=['GET'])
def shows_search():
    query = request.args.get('q', '')
    if query:
        shows = search_tv_shows(query)
    else:
        shows = get_popular_tv_shows()
    
    return render_template('shows_search.html', shows=shows, search_query=query)

@main.route('/show/<int:show_id>')
def show_details(show_id):
    show_data = get_tv_show_details(show_id)
    show = {
        'id': show_data['id'],
        'title': show_data['name'],
        'poster_url': f"https://image.tmdb.org/t/p/w500{show_data['poster_path']}" if show_data['poster_path'] else None,
        'info': show_data['overview'],
        'seasons': [
            {
                'season_number': season['season_number'],
                'name': season['name'],
                'episodes': fetch_season_episodes(show_id, season['season_number'])
            }
            for season in show_data['seasons']
        ]
    }
    return render_template('show.html', show=show)

@main.route('/show/<int:show_id>/season/<int:season_number>/episode/<int:episode_number>')
def episode_details(show_id, season_number, episode_number):
    poster_url = fetch_show_poster(show_id, season_number)
    episode = fetch_episode_details(show_id, season_number, episode_number)
    show_data = get_tv_show_details(show_id)
    show = {
        'id': show_data['id'],
        'title': show_data['name']
    }
    return render_template('episode.html', episode=episode, show_id=show_id, episode_number=episode_number, season_number=season_number, poster_url=poster_url, show=show)

@main.route('/login', methods=['GET', 'POST'])
def login():
    global USER_ID

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id  # Use 'user_id' to store user identifier
            USER_ID = user.id
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
        elif User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
        else:
            new_user = User(username=username, password=generate_password_hash(password), email=email)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('main.login'))

    return render_template('register.html')

@main.route('/logout')
def logout():
    global USER_ID

    session.pop('username', None)
    session.pop('user_id', None)
    USER_ID = None


    flash('You have been logged out', 'success')
    return redirect(url_for('main.home'))

@main.route('/comments', methods=['GET'])
def get_comments():
    media_id = request.args.get('media_id')
    timestamp = int(request.args.get('timestamp'))
    media_type = request.args.get('media_type')

    comments = db.session.query(Comment).join(Media).filter(Media.id == media_id, Comment.timestamp == int(timestamp)).all()
    comment_data = [{'username': comment.user.username, 'text': comment.text} for comment in comments]

    return jsonify(comment_data)

@main.route('/comments_show', methods=['GET'])
def get_comments_show():
    media_id = request.args.get('media_id')
    timestamp = int(request.args.get('timestamp'))
    #media_type = request.args.get('media_type')
    season_number = request.args.get('season_number')
    episode_number = request.args.get('episode_number')

    print("#2")
    print(timestamp)
    #print(unique_id)
    #print(media_title)
    print(media_id)
    #print(media_type)
    print(season_number)
    print(episode_number)
    #print(episode_title)
    

    

    comments = db.session.query(Comment).join(Media).filter(Media.id == media_id, Comment.season_number == int(season_number), Comment.episode_number == int(episode_number), Comment.timestamp == timestamp).all()
    print(comments)
    comment_data = [{'username': comment.user.username, 'text': comment.text} for comment in comments]

    return jsonify(comment_data)

@main.route('/submit_comment', methods=['POST'])
def submit_comment():
    # Retrieve necessary variables from form or URL parameters
    media_title = request.args.get('media_title', None)
    media_id = request.args.get('media_id', None) # this goes in Media.id variable
    media_type = request.args.get('media_type', None)

    # Check if user is signed in (session check)
    if 'user_id' not in session:
        return redirect(url_for('main.login'))  # Redirect to login page if user is not logged in

    # Obtain necessary variables from session and form
    user_id = session['user_id']
    timestamp = request.form.get('timestamp')
    text = request.form.get('text')

    # Find the user and media objects (create media if not found)
    user = db.session.query(User).filter(User.id == user_id).first()
    media = db.session.query(Media).filter(Media.id == media_id).first()
    print(media)

    if not media:
        # Create a new media object if not found
        print('media created')
        media = Media(id=media_id, title=media_title, media_type=media_type)
        db.session.add(media)
        db.session.commit()

    # Create a new comment object and associate it with the user and media
    if user and media:
        new_comment = Comment(user_id=user.id, media_id=media.unique_id, timestamp=int(timestamp), text=text)
        db.session.add(new_comment)
        db.session.commit()

        # Redirect to a success page or return a JSON response indicating success
        return jsonify({'message': 'Comment submitted successfully'})

    # Handle error or invalid request
    return jsonify({'error': 'Failed to submit comment'}), 400  # Return a JSON error response with status code 400


@main.route('/account')
def account():
    user_id = session.get('user_id')  # Get the logged-in user's ID from the session

    # Fetch user details
    user = User.query.get(user_id)
    # unique_id = '629DixmZGHc7ILtEntuiWE'
    ratings = Rating.query.filter_by(user_id=user_id).all()
    comments = Comment.query.filter_by(user_id=user_id).all()
    # media = Media.query.filter_by(id=unique_id).all()

    # print(ratings)
    # print(comments)
    # print(((ratings[8]).media_id))
    # print(media)
    # # Fetch media titles for ratings
    # ratings_with_titles = [(rating, Media.query.get(rating.media_id).title) for rating in ratings]

    # # Fetch media titles for comments
    # comments_with_titles = [(comment, Media.query.get(comment.media_id).title) for comment in comments]
    # print(ratings_with_titles)
    # print(comments_with_titles)
    return render_template('account.html', user=user, ratings=ratings, comments=comments)


@main.record_once
def register_template_filters(state):
    app = state.app
    @app.template_filter('timestamp_to_hms')
    def timestamp_to_hms_filter(seconds):
        return str(timedelta(seconds=seconds))
