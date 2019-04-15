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
import collections
from math import pi
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, abort, flash
from werkzeug.security import generate_password_hash, check_password_hash

# Bokeh Imports
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.transform import dodge, cumsum
from bokeh.core.properties import value
from bokeh.models import ColumnDataSource
from bokeh.palettes import Category20c

# Pandas
import pandas as pd

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
@app.route('/', methods=['GET', 'POST'])
def index(tab="teams", players=[], pinfo=collections.OrderedDict(), curr_tid=-1):
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

        if curr_tid == -1:
            curr_tid = int(session['tid'])

        ########################################################
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
            if result[0] == curr_tid:
                team_name = result[1]
        rank_cursor.close()

        user_cursor = g.conn.execute(""" SELECT  userid, name 
                                                FROM    users
                                                WHERE   admin_flag = 'f'
                                                """)
        user_dict = dict()
        for result in user_cursor:
            user_dict[result[0]] = result[1]

        user_cursor.close()
        ########################################################

        ########################################################
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

        ########################################################
        # Win-Draw-Loss Plot
        cmd = """ WITH mymatches AS 
                ( 
                    SELECT    * 
                    FROM      Matches
                    WHERE     team1 = :tid
                    OR        team2 = :tid
                ),
                home_matches AS
                (
                    SELECT  a.*
                    FROM    mymatches a,
                            Teams b
                    WHERE   b.tid = :tid
                    AND     a.venue = b.home
                ),
                away_matches AS
                (
                    SELECT  a.*
                    FROM    mymatches a,
                            Teams b
                    WHERE   b.tid = :tid
                    AND     a.venue != b.home
                )
                
                SELECT  'All' AS Venue, a.wins, b.losses, c.total - a.wins - b.losses AS draws
                FROM    (
                            SELECT  SUM(a.wins) AS wins
                            FROM    (
                                        SELECT  COUNT(*) AS wins
                                        FROM    mymatches
                                        WHERE   team1 = :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS wins
                                        FROM    mymatches
                                        WHERE   team2 = :tid
                                        AND     winner = 2
                                    ) a
                        ) a,
                        (
                            SELECT  SUM(a.losses) AS losses
                            FROM    (
                                        SELECT  COUNT(*) AS losses
                                        FROM    mymatches
                                        WHERE   team1 <> :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS losses
                                        FROM    mymatches
                                        WHERE   team2 <> :tid
                                        AND     winner = 2
                                    ) a
                        ) b,
                        (
                            SELECT  COUNT(*) AS total
                            FROM    mymatches
                        ) c
                UNION ALL
                SELECT  'Home' AS Venue, a.wins, b.losses, c.total - a.wins - b.losses AS draws
                FROM    (
                            SELECT  SUM(a.wins) AS wins
                            FROM    (
                                        SELECT  COUNT(*) AS wins
                                        FROM    home_matches
                                        WHERE   team1 = :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS wins
                                        FROM    home_matches
                                        WHERE   team2 = :tid
                                        AND     winner = 2
                                    ) a
                        ) a,
                        (
                            SELECT  SUM(a.losses) AS losses
                            FROM    (
                                        SELECT  COUNT(*) AS losses
                                        FROM    home_matches
                                        WHERE   team1 <> :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS losses
                                        FROM    home_matches
                                        WHERE   team2 <> :tid
                                        AND     winner = 2
                                    ) a
                        ) b,
                        (
                            SELECT  COUNT(*) AS total
                            FROM    home_matches
                        ) c
                UNION ALL
                SELECT  'Away' AS Venue, a.wins, b.losses, c.total - a.wins - b.losses AS draws
                FROM    (
                            SELECT  SUM(a.wins) AS wins
                            FROM    (
                                        SELECT  COUNT(*) AS wins
                                        FROM    away_matches
                                        WHERE   team1 = :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS wins
                                        FROM    away_matches
                                        WHERE   team2 = :tid
                                        AND     winner = 2
                                    ) a
                        ) a,
                        (
                            SELECT  SUM(a.losses) AS losses
                            FROM    (
                                        SELECT  COUNT(*) AS losses
                                        FROM    away_matches
                                        WHERE   team1 <> :tid
                                        AND     winner = 1
                                        UNION ALL
                                        SELECT  COUNT(*) AS losses
                                        FROM    away_matches
                                        WHERE   team2 <> :tid
                                        AND     winner = 2
                                    ) a
                        ) b,
                        (
                            SELECT  COUNT(*) AS total
                            FROM    away_matches
                        ) c """
        wld_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        win_loss_draw = dict()
        for result in wld_cursor:
            win_loss_draw[result[0]] = [result[1], result[2], result[3]]
        wld_cursor.close()

        # Bokeh Plot

        venues = ['Home', 'Away', 'All']

        wld_data = {'venue': list(win_loss_draw.keys()),
                    'wins': [win_loss_draw[i][0] for i in list(win_loss_draw.keys())],
                    'losses': [win_loss_draw[i][1] for i in list(win_loss_draw.keys())],
                    'draws': [win_loss_draw[i][2] for i in list(win_loss_draw.keys())]
                    }

        source = ColumnDataSource(data=wld_data)

        p = figure(x_range=venues, y_range=(0, 20), plot_height=500,
                   title="Performance of {} over venues".format(team_name))

        p.vbar(x=dodge('venue', -0.125, range=p.x_range), top='wins', width=0.2, source=source,
               color="#c9d9d3", legend=value("Wins"))

        # if sum(wld_data['draws']) != 0:
        #     p.vbar(x=dodge('venue', 0.0, range=p.x_range), top='draws', width=0.2, source=source,
        #            color="#718dbf", legend=value("Draws"))

        p.vbar(x=dodge('venue', 0.125, range=p.x_range), top='losses', width=0.2, source=source,
               color="#e84d60", legend=value("Losses"))

        p.xaxis[0].axis_label = 'Venue'
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
        cmd = """   SELECT  pid, name, runs, SUM(runs) OVER (PARTITION BY tid) AS total_runs, country
                    FROM    players 
                    WHERE   tid = :tid
                    ORDER BY runs DESC
                    LIMIT 3 """
        bat_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        top_batsmen = collections.OrderedDict()
        for result in bat_cursor:
            top_batsmen[result[0]] = [result[1], result[2], result[2] * 100 / float(result[3]), result[4]]
        bat_cursor.close()

        # # Bowlers
        cmd = """   SELECT  pid, name, wickets, SUM(wickets) OVER (PARTITION BY tid) AS total_wickets, country
                    FROM    players 
                    WHERE   tid = :tid
                    ORDER BY wickets DESC
                    LIMIT 3 """
        bowl_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        top_bowlers = collections.OrderedDict()
        for result in bowl_cursor:
            top_bowlers[result[0]] = [result[1], result[2], result[2] * 100 / float(result[3]), result[4]]
        bowl_cursor.close()
        ########################################################

        ########################################################
        # Team Composition Pie
        cmd = """   SELECT  country, count(*)
                    FROM    players
                    WHERE   tid = :tid
                    GROUP BY country
                    ORDER BY count(*) DESC  """
        team_comp_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        team_comp = dict()
        for result in team_comp_cursor:
            team_comp[result[0]] = result[1]
        team_comp_cursor.close()

        # Bokeh Plot
        data = pd.Series(team_comp).reset_index(name='value').rename(columns={'index': 'country'})
        data['angle'] = data['value'] / data['value'].sum() * 2 * pi
        data['color'] = Category20c[len(team_comp)]

        p = figure(plot_height=500, title="Player Diversity", toolbar_location=None,
                   tools="hover", tooltips="@country: @value", x_range=(-0.5, 1.0))

        p.wedge(x=0, y=1, radius=0.4,
                start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
                line_color="white", fill_color='color', legend='country', source=data)

        p.axis.axis_label = None
        p.axis.visible = False
        p.grid.grid_line_color = None

        team_comp_plot_script, team_comp_plot_div = components(p)
        ########################################################

        ########################################################
        # Last 5 matches
        cmd = """
                WITH mymatches AS
                (
                    SELECT  *
                    FROM    matches
                    WHERE   team1 = :tid
                    OR      team2 = :tid
                )
                SELECT  a.mid,
                        b.name AS Opp,
                        a.win_lose,
                        a.venue,
                        a.type
                FROM    (
                            SELECT  mid,
                                    team2 AS Opposition,
                                    CASE
                                        WHEN winner = 1 THEN 'won'
                                        ELSE 'lost' 
                                    END AS win_lose,
                                    venue,
                                    type
                            FROM    mymatches
                            WHERE   team1 = :tid
                            UNION ALL
                            SELECT  mid,
                                    team1 AS Opposition,
                                    CASE
                                        WHEN winner = 2 THEN 'won'
                                        ELSE 'lost' 
                                    END AS win_lose,
                                    venue,
                                    type
                            FROM    mymatches
                            WHERE   team2 = :tid
                        ) AS a,
                        Teams AS b
                WHERE   a.Opposition = b.tid
                ORDER BY mid DESC
                LIMIT 5 """

        last_matches_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        last_matches = collections.OrderedDict()
        for result in last_matches_cursor:
            last_matches[result[0]] = [result[1], result[2], result[3], result[4]]
        last_matches_cursor.close()

        # last_matches = collections.OrderedDict(sorted(last_matches.items()))
        ########################################################

        ########################################################
        # Match-by-match plot
        cmd = """
                WITH mymatches AS
                (
                    SELECT  *
                    FROM    matches
                    WHERE   team1 = :tid
                    OR      team2 = :tid
                ),
                wins_losses AS
                (
                    SELECT	mid,
                            team2 AS Opposition,
                            CASE
                                WHEN winner = 1 THEN 1
                                ELSE 0
                            END AS win_lose,
                            venue,
                            type
                    FROM    mymatches
                    WHERE   team1 = :tid
                    UNION ALL
                    SELECT  mid,
                            team1 AS Opposition,
                            CASE
                                WHEN winner = 2 THEN 1
                                ELSE 0
                            END AS win_lose,
                            venue,
                            type
                    FROM    mymatches
                    WHERE   team2 = :tid
                )
                SELECT	mid,
                        SUM(win_lose) OVER (ORDER BY mid)
                FROM	wins_losses
                ORDER BY mid """

        matches_cursor = g.conn.execute(text(cmd), tid=curr_tid)

        matches = collections.OrderedDict()
        j = 0
        for result in matches_cursor:
            # print(result)
            j += 1
            matches[j] = result[1]
        matches_cursor.close()

        plot = figure(plot_height=500,title="Performance of {} per match".format(team_name))

        x = list(matches.keys())
        y = [matches[i] for i in list(matches.keys())]

        plot.line(x, y, line_width=4)

        plot.xaxis[0].axis_label = 'Match Number'
        plot.yaxis[0].axis_label = 'Wins'

        matches_plot_script, matches_plot_div = components(plot)
        ########################################################

        #######################################################
        # Admin page tournament list
        tournament_cursor = g.conn.execute("select * from tournament")
        tournament_dict = {}
        for tourn in tournament_cursor:
            tournament_dict[tourn[0]] = [tourn[1], tourn[2], tourn[3]]
        tournament_cursor.close()
        #######################################################

        #######################################################
        # Players info


        #######################################################

        context = dict()
        context['name'] = session['username']
        context['tid'] = session['tid']
        context['selected_tid'] = curr_tid

        if session['admin']:
            return render_template("adminfile.html", data=context, users=user_dict, tournament=tournament_dict)
        else:
            return render_template("anotherfile.html", tab=tab, data=context, rankings=rankings, last_matches=last_matches,
                                   wld_plot_script=wld_plot_script, wld_plot_div=wld_plot_div,
                                   top_batsmen=top_batsmen, top_bowlers=top_bowlers,
                                   team_comp_plot_script=team_comp_plot_script, team_comp_plot_div=team_comp_plot_div,
                                   matches_plot_script=matches_plot_script, matches_plot_div=matches_plot_div,
                                   players=players, pinfo=pinfo)


@app.route('/change_view', methods=['POST'])
def change_view():

    selected_tid = int(request.form['tid'])

    return index(curr_tid=selected_tid)


@app.route('/player_search', methods=['POST'])
def player_search():

    player_names = []
    pinfo = collections.OrderedDict()

    # Get search term
    search_term = request.form['player']

    # If empty string in search, raise error
    if not search_term:
        too_broad_msg = 'No search query entered'
        flash(too_broad_msg)
    else:
        # Do contains search in players relation
        cmd = """
                SELECT  pid, name
                FROM    Players
                WHERE   name ILIKE :search_term
                """
        search_cursor_count = g.conn.execute(text(cmd), search_term=('%' + search_term + '%')).rowcount

        # If too many results, again raise error
        if search_cursor_count > 20:
            too_broad_msg = 'Search too broad. Be more specific'
            flash(too_broad_msg)
        # If no result, raise error
        elif search_cursor_count == 0:
            no_player_msg = 'No player found'
            flash(no_player_msg)
        else:
            search_results = g.conn.execute(text(cmd), search_term=('%' + search_term + '%'))

            for name in search_results:
                player_names.append([name[0], name[1]])

            player_names.sort()

    return index('players', player_names, pinfo, int(session['tid']))


@app.route('/player_info', methods=['POST'])
def player_info():

    pinfo = collections.OrderedDict()
    player_names = []

    print("PID is {}".format(request.form['pid']))

    pid = request.form['pid']

    if pid:
        tab = "players"

    cmd = """
            SELECT  a.name, a.age,
                    a.runs, a.wickets,
                    b.name, a.since,
                    a.country, COALESCE(c.name, 'NONE')
            FROM    Players a
            INNER JOIN
                    Teams b
            ON      a.tid = b.tid
            LEFT JOIN
                    Award c
            ON      a.pid = c.pid
            WHERE   a.pid = :pid
            """
    player_info_cursor = g.conn.execute(text(cmd), pid=int(pid))

    for info in player_info_cursor:
        pinfo['name'] = info[0]
        pinfo['age'] = info[1]
        pinfo['country'] = info[6]
        pinfo['team'] = info[4]
        pinfo['since'] = info[5]
        pinfo['runs'] = info[2]
        pinfo['wickets'] = info[3]
        pinfo['award'] = info[7]
        # Define primary role
        if pinfo['runs'] > 3000:
            if pinfo['wickets'] < 100:
                pinfo['role'] = "Batsman"
            else:
                pinfo['role'] = "All-rounder"
        else:
            pinfo['role'] = "Bowler"

    print(pinfo)

    return index('players', player_names, pinfo, curr_tid=int(session['tid']))


@app.route('/login', methods=['POST'])
def login():
    # Store username and password
    session['username'] = request.form['username']
    session['password'] = request.form['password']

    # Check if username exists in Database (case sensitive)
    cmd = """
            SELECT  name, password, admin_flag, tid
            FROM    Users
            WHERE   name = :username
            """
    cursor = g.conn.execute(text(cmd), username=session['username'])

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

    return redirect('/')


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('password', None)
    session['logged_in'] = False
    return redirect('/')


@app.route('/profile')
def profile():
    team_cursor = g.conn.execute("SELECT tid, name FROM teams WHERE tid < 9 ORDER BY tid")
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

    # print("Reached")

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
    team_cursor = g.conn.execute("SELECT tid, name FROM teams WHERE tid < 9 ORDER BY tid")
    teams = dict()
    for result in team_cursor:
        teams[result['tid']] = result['name']
    team_cursor.close()

    # Debug
    # print(teams)

    return render_template('signup.html', team_list=teams)


@app.route("/user_update", methods=['POST'])
def user_update():
    # print "Reached"
    user = request.form.get("userId")
    print('---------------------------------------'
          '----------------------------------------'
          '----------------------------------')
    print('Deleteting userid ', str(user))
    print('-------------------------------------------'
          '--------------------------------------------'
          '--------------------------')

    cmd = """DELETE FROM Users where userid = :user_id"""
    g.conn.execute(text(cmd), user_id=user)
    # return redirect("/")
    return index(curr_tid=int(session['tid']))


@app.route("/tournament_delete", methods=['POST'])
def tournament_delete():
    # print "Reached"
    tour_id = request.form.get("tourId")
    print('---------------------------------------'
          '----------------------------------------'
          '----------------------------------')
    print('Deleteting tourid ', str(tour_id))
    print('-------------------------------------------'
          '--------------------------------------------'
          '--------------------------')

    cmd = """DELETE FROM Tournament where TourID = :tourid"""
    g.conn.execute(text(cmd), tourid=tour_id)
    # return redirect("/")
    return index(curr_tid=int(session['tid']))


@app.route("/tournament_update", methods=['POST'])
def tournament_update():
    # print "Reached"
    sponser_name = request.form.get("Sponser")
    tourn_year = request.form.get("Year")
    print('---------------------------------------'
          '----------------------------------------'
          '----------------------------------')
    print('Sponser ', str(sponser_name))
    print('Year', tourn_year)
    print('-------------------------------------------'
          '--------------------------------------------'
          '--------------------------')

    try:
        int(tourn_year)
    except Exception:
        flash("Enter a valid year")
        return index(curr_tid=int(session['tid']))

    if len(tourn_year) != 0:
        if int(tourn_year) <= 2019:
            flash("Tournament has finished. Please consider sponsoring in the future ")
            return index(curr_tid=int(session['tid']))
        else:
            cmd = """
                    SELECT  year 
                    FROM    tournament 
                    WHERE   year = :year
                    """
            year_check_cursor = g.conn.execute(text(cmd), year=tourn_year)

            if year_check_cursor.rowcount:
                flash("Tournament already has a sponsor")
                return index(curr_tid=int(session['tid']))

    if len(sponser_name)== 0:
        flash("Enter a valid tournament name, greater than 0 characters")
    else:
        cmd = """SELECT * FROM tournament ORDER BY TourID DESC LIMIT 1"""
        tournament_cursor = g.conn.execute(text(cmd))
        for row in tournament_cursor:
            curr_id = row[0] + 1
            if len(tourn_year) == 0:
                tournament_year = row[2] + 1
            else:
                tournament_year = tourn_year
            sponser = sponser_name
            tournament_name = sponser + ' IPL'
        print('---------------------------------------'
              '----------------------------------------'
              '----------------------------------')
        print("Information is ", curr_id, tournament_year, sponser, tournament_name)
        print('---------------------------------------'
              '----------------------------------------'
              '----------------------------------')
        cmd = """INSERT INTO Tournament(TourID, Name, Year, SponsorName)
                        VALUES (:tourid, :tourname, :touryear, :sponsor)"""
        g.conn.execute(text(cmd), tourid=curr_id, tourname=tournament_name,
                       touryear=tournament_year, sponsor=sponser)
        flash("Tournament Created")

    return redirect("/")


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
    cmd = "SELECT name FROM Users WHERE name = :username"
    user_cursor = g.conn.execute(text(cmd), username=username)
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
