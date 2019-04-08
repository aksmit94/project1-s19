#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

    python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, abort, flash
from werkzeug.security import generate_password_hash, check_password_hash

# Bokeh Imports
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import components
from bokeh.transform import dodge
from bokeh.core.properties import value
from bokeh.models import ColumnDataSource

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# Setup secret key for session
app.secret_key = os.urandom(12)



# XXX: The Database URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@<IP_OF_POSTGRE_SQL_SERVER>/<DB_NAME>
#
# For example, if you had username ewu2493, password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://ewu2493:foobar@<IP_OF_POSTGRE_SQL_SERVER>/postgres"
#
# For your convenience, we already set it to the class database

# Use the DB credentials you received by e-mail
DB_USER = "aj2844"
DB_PASSWORD = "fLS4UlT3SG"

DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"

DATABASEURI = "postgresql://"+DB_USER+":"+DB_PASSWORD+"@"+DB_SERVER+"/w4111"


#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)


# Here we create a test table and insert some values in it
# engine.execute("""DROP TABLE IF EXISTS test;""")
# engine.execute("""CREATE TABLE IF NOT EXISTS test (
#   id serial,
#   name text
# );""")
# engine.execute("""INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace');""")



@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request

    The variable g is globally accessible
    """
    try:
        g.conn = engine.connect()
    except:
        print "uh oh, problem connecting to database"
        import traceback; traceback.print_exc()
        g.conn = None


@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#  #
# Flask uses Jinja templates, which is an extension to HTML where you can
# pass data to a template and dynamically generate HTML based on the data
# (you can think of it as simple PHP)
# documentation: https://realpython.com/blog/python/primer-on-jinja-templating/
#
# You can see an example template in templates/index.html
#
# context are the variables that are passed to the template.
# for example, "data" key in the context variable defined below will be
# accessible as a variable in index.html:
#
#     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
#     <div>{{data}}</div>
#
#     # creates a <div> tag for each element in data
#     # will print:
#     #
#     #   <div>grace hopper</div>
#     #   <div>alan turing</div>
#     #   <div>ada lovelace</div>
#     #
#     {% for n in data %}
#     <div>{{n}}</div>
#     {% endfor %}
#
@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    # print request.args

    if not session.get('logged_in'):
        return render_template('landing.html')
    else:
        # Ranking table
        rank_cursor = g.conn.execute(""" SELECT  a.tid, a.name, b.rank 
                                        FROM    Teams a, Ranking b 
                                        WHERE   a.tid = b.tid
                                        AND     b.tourid = 1 
                                        ORDER BY b.rank """)
        rankings = dict()
        for result in rank_cursor:
            rankings[result[2]] = [result[0], result[1]]

            # Store fav team name for future reference
            if result[0] == session['tid']:
                fav_team_name = result[1]
        rank_cursor.close()




        # # Players info
        # player_cmd = """   SELECT   pid, players.name, age,
        #                             runs, wickets, b.tid,
        #                             b.name as team_name, players.since, players.till,
        #                             dense_rank() OVER (ORDER BY runs DESC) AS run_rank,
        #                             dense_rank() OVER (ORDER BY wickets DESC) AS wicket_rank
        #                     FROM    players, teams as b
        #                     WHERE   players.tid = b.tid
        #                     AND     pid = :pid """
        # player = g.conn.execute(text(player_cmd), pid=int(pid))


        ########################################################
        # Win-Draw-Loss Plot
        cmd = """ WITH mymatches AS 
                ( 
                    SELECT    * 
                    FROM      Matches
                    WHERE     team1 = :fav_tid 
                    OR        team2 = :fav_tid
                )
                SELECT  a.wins, b.losses, c.total - a.wins - b.losses AS draws
                FROM    (
                            SELECT  SUM(a.wins) AS wins
                            FROM    (
                                        SELECT  COUNT(*) AS wins
                                        FROM    mymatches
                                        WHERE   team1 = :fav_tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS wins
                                        FROM    mymatches
                                        WHERE   team2 = :fav_tid
                                        AND     winner = 2
                                    ) a
                        ) a,
                        (
                            SELECT  SUM(a.losses) AS losses
                            FROM    (
                                        SELECT  COUNT(*) AS losses
                                        FROM    mymatches
                                        WHERE   team1 <> :fav_tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS losses
                                        FROM    mymatches
                                        WHERE   team2 <> :fav_tid
                                        AND     winner = 2
                                    ) a
                        ) b,
                        (
                            SELECT  COUNT(*) AS total
                            FROM    mymatches
                        ) c """
        wld_cursor = g.conn.execute(text(cmd), fav_tid=int(session['tid']))

        win_loss_draw = dict()
        for result in wld_cursor:
            win_loss_draw['wins'] = result[0]
            win_loss_draw['losses'] = result[1]
            win_loss_draw['draws'] = result[2]
            win_loss_draw['total_games'] = sum(result)
        wld_cursor.close()

        # Bokeh Plot
        wld_data = {'season': ['2008'],
                    'wins': [win_loss_draw['wins']],
                    'draws': [win_loss_draw['draws']],
                    'losses': [win_loss_draw['losses']]}

        source = ColumnDataSource(data=wld_data)

        p = figure(x_range=['2008'], y_range=(0, int(win_loss_draw['total_games'])), plot_height=500,
                   title="Performance of {} over seasons".format(fav_team_name))

        p.vbar(x=dodge('season', -0.125, range=p.x_range), top='wins', width=0.2, source=source,
               color="#c9d9d3", legend=value("wins"))

        if win_loss_draw['draws'] != 0:
            p.vbar(x=dodge('season', 0.0, range=p.x_range), top='draws', width=0.2, source=source,
                   color="#718dbf", legend=value("draws"))

        p.vbar(x=dodge('season', 0.125, range=p.x_range), top='losses', width=0.2, source=source,
               color="#e84d60", legend=value("losses"))

        p.xaxis[0].axis_label = 'Season'
        p.yaxis[0].axis_label = 'No. of Games'

        p.x_range.range_padding = 0.1
        p.xgrid.grid_line_color = None
        p.legend.location = "top_left"
        p.legend.orientation = "horizontal"

        wld_plot_script, wld_plot_div = components(p)
        ########################################################

        ########################################################
        # Top performers

        # # Batsmen
        cmd = """   SELECT  pid, name, runs, SUM(runs) OVER (PARTITION BY tid) AS total_runs
                    FROM    players 
                    WHERE   tid = :tid
                    ORDER BY runs DESC
                    LIMIT 3 """
        bat_cursor = g.conn.execute(text(cmd), tid=session['tid'])

        top_batsmen = dict()
        for result in bat_cursor:
            top_batsmen[result[0]] = [result[1], result[2], result[2] * 100 / float(result[3])]
        bat_cursor.close()

        # # Bowlers
        cmd = """   SELECT  pid, name, wickets, SUM(wickets) OVER (PARTITION BY tid) AS total_wickets
                    FROM    players 
                    WHERE   tid = :tid
                    ORDER BY wickets DESC
                    LIMIT 3 """
        bowl_cursor = g.conn.execute(text(cmd), tid=session['tid'])

        top_bowlers = dict()
        for result in bowl_cursor:
            top_bowlers[result[0]] = [result[1], result[2], result[2] * 100 / float(result[3])]
        bowl_cursor.close()
        ########################################################
        context = dict()
        context['name'] = session['username']
        context['tid'] = session['tid']

        if session['admin']:
            return render_template("anotherfile.html", data=context, rankings=rankings)
        else:
            return render_template("anotherfile.html", data=context, rankings=rankings,
                                   plot_script=wld_plot_script, plot_div=wld_plot_div,
                                   top_batsmen=top_batsmen, top_bowlers=top_bowlers)
        #
        # This is an example of a different path.  You can see it at
        #
        #     localhost:8111/another
        #
        # notice that the functio name is another() rather than index()
        # the functions for each app.route needs to have different names
        #
        # @app.route('/another')
        # def another():
        #   return render_template("anotherfile.html")


# Example of adding new data to the database
# @app.route('/add', methods=['POST'])
# def add():
#     name = request.form['name']
#     print name
#     cmd = 'INSERT INTO test(name) VALUES (:name1), (:name2)';
#     g.conn.execute(text(cmd), name1 = name, name2 = name);
#     return redirect('/')


@app.route('/login', methods=['POST'])
def login():
    # Store username and password
    session['username'] = request.form['username']
    session['password'] = request.form['password']

    # Check if username exists in Database (case sensitive)
    cursor = g.conn.execute("SELECT name, password, admin_flag, tid FROM Users WHERE name = %s", (session['username']))

    if cursor.rowcount == 0:
        # Create username not found string
        not_found = "Username {} not found in Database".format(session['username'])
        flash(not_found)
    else:
        # define dict to retrieve user info from DB
        db_user = dict()
        result = cursor.fetchone()
        db_user['password'] = result['password']
        db_user['admin'] = result['admin_flag']
        db_user['tid'] = result['tid']
        cursor.close()

        # After hashing implemented
        # if check_password_hash(db_user['password'], session['password']):
        #     session['logged_in'] = True
        #     session['admin'] = db_user['admin']
        # else:
        #     flash('wrong password!')

        if session['password'] == db_user['password']:
            session['logged_in'] = True
            session['admin'] = db_user['admin']
            session['tid'] = db_user['tid']
        else:
            flash('wrong password!')
    return index()


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('password', None)
    session['logged_in'] = False
    return redirect('/')


@app.route('/profile')
def profile():
    team_cursor = g.conn.execute("SELECT tid, name FROM teams ORDER BY tid")
    teams = dict()
    for result in team_cursor:
        teams[result['tid']] = result['name']
    team_cursor.close()

    context = dict()
    context['name'] = session['username']
    context['tid'] = session['tid']

    return render_template('profile.html', team_list=teams, user_info=context)


@app.route('/profile', methods=['POST'])
def profile_update():

    print("Reached")

    # helper functions
    fav_team = int(request.form['favorite_team'])
    admin_flag = str(0)

    print('---------------------------------------'
          '----------------------------------------'
          '----------------------------------')
    print('favorite tid: ', str(fav_team))
    print('-------------------------------------------'
          '--------------------------------------------'
          '--------------------------')

    username = session['username']

    # Update Query
    cmd = """UPDATE Users SET tid = :fav_team where name = :user"""

    # Check if username exists
    g.conn.execute(text(cmd), user=username, fav_team=fav_team)
    session['tid'] = fav_team

    return redirect("/")


@app.route('/signup')
def signup():

    # Get team list to populate dropdown
    team_cursor = g.conn.execute("SELECT tid, name FROM teams ORDER BY tid")
    teams = dict()
    for result in team_cursor:
        teams[result['tid']] = result['name']
    team_cursor.close()

    # Debug
    # print(teams)

    return render_template('signup.html', team_list=teams)


@app.route('/signup', methods=['POST'])
def signup_form():

    # helper functions
    def check_username(username):
        return username.isalnum()

    def check_password(password, confirm_password):
        if len(password) < 6:
            return 0
        elif password != confirm_password:
            return 1
        else:
            return 2

    username = str(request.form['username'])
    password = str(request.form['password'])
    confirm_pass = str(request.form['confirm_password'])
    fav_team = int(request.form['favorite_team'])
    admin_flag = str(0)

    print('---------------------------------------'
          '----------------------------------------'
          '----------------------------------')
    print("Username= ", username, "\n password= ",
          password, "\n confirm pass: ", confirm_pass,
          '\n favorite tid: ', str(fav_team))
    print('-------------------------------------------'
          '--------------------------------------------'
          '--------------------------')

    # Check username
    if not check_username(username):
        flash("Username should be Alpha-Numeric")
        return redirect('/signup')

    # Check password
    check = check_password(password, confirm_pass)
    if check != 2:
        if check == 0:
            flash("Password length should be 6 or more")
        else:
            flash("Passwords do not match")
        return redirect('/signup')

    # Check if username exists
    user_cursor = g.conn.execute("SELECT name FROM Users WHERE name = %s", username)
    if not user_cursor.rowcount:
        # Get max existing id
        #   # Note: Change schema of tables to make IDs serialized
        id_cursor = g.conn.execute("SELECT MAX(userid) AS maxid FROM Users")
        result = id_cursor.fetchone()
        id_cursor.close()
        max_id = int(result['maxid'])
        curr_id = max_id + 1

        # Hash password
        # password = generate_password_hash(password)

        # Insert query
        cmd = """INSERT INTO Users(userid, name, password, admin_flag, tid) 
                VALUES (:userid, :name, :password, :admin_flag, :fav_team)"""
        g.conn.execute(text(cmd), userid=curr_id, name=username, password=password,
                       admin_flag=admin_flag, fav_team=fav_team)
        flash("Account created. You may now login")
    else:
        flash("Username already taken :(")
        return redirect('/signup')
    user_cursor.close()

    return redirect('/')


if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using

            python server.py

        Show the help text using

            python server.py --help

        """

        HOST, PORT = host, port
        print "running on %s:%d" % (HOST, PORT)
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


    run()
