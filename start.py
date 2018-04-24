import datetime, math, optparse, os, re, sys, threading, time, webbrowser, urllib, sqlite3,hashlib
from collections import namedtuple, OrderedDict 
from flask import Flask, abort, escape, flash, jsonify, make_response, Markup, redirect,render_template, request, session, url_for, g,send_file
from pygments import formatters, highlight, lexers



from peewee import *



CUR_DIR = os.path.realpath(os.path.dirname(__file__))
DEBUG = True
MAX_RESULT_SIZE = 1000
ROWS_PER_PAGE = 100
SECRET_KEY = 'maynooth_university'
# special_characters=[['u̯', 'i̯', 'm̄', 'ḟ', '·'], 
#                     ['ȩ', '⁊', 'ɫ', 'Ȩ', 'ṡ'], 
#                     ['ā', 'ē', 'ī', 'ō', 'ū'], 
#                     ['ä', 'ë', 'ï', 'ö', 'ü'], 
#                     ['ă', 'ĕ', 'ĭ', 'ŏ', 'ŭ'], 
#                     ['æ', 'Æ', 'ʒ', 'đ', 'ɔ̄'], 
#                     ['φ', 'þ', 'β', '˜', 'χ'], 
#                     ['γ', '∅', 'ə', 'ɛ', 'ƀ'], 
#                     ['θ', 'ð', 'ɣ', 'ɸ', 'β']]



app = Flask(
    __name__,
    static_folder=os.path.join(CUR_DIR, 'static'),
    template_folder=os.path.join(CUR_DIR, 'templates'))
app.config.from_object(__name__)
dataset = None
migrator = None

# other functions

# end of other functions




    

#
# Flask views.
#
@app.template_filter('url_encoder')
def url_encoder(strs):
    return urllib.parse.quote(strs)

@app.template_filter('url_decoder')
def url_encoder(strs):
    return urllib.parse.unquote(strs)

@app.template_filter('error_newline')
def error_newline(strs):
    return strs.replace('#$#','<br>')

@app.template_filter('range_list_length')
def range_list_length(source_list):
    return list(range(len(source_list)))
@app.template_filter('hide_primary_key_colunms')
def hide_primary_key_colunms(source_list):
    return source_list[1:]

@app.template_filter('remove_underline')
def remove_underline(strs):
    return strs.replace('_',' ')


# @app.errorhandler(404)
# def page404(e):
#     error_mes='You have been redirected to homepage because an error occurs, please see the detail:#$# %s'%(e)
#     print(error_mes)
#     flash(error_mes)
#     return redirect(url_for('index'))

# @app.errorhandler(500)
# def page500(e):
#     error_mes='You have been redirected to homepage because an error occurs, please see the detail:#$# %s'%(e)
#     print(error_mes)
#     flash(error_mes)
#     return redirect(url_for('index'))

#tbl_morphology
tbl_morphology="MORPHOLOGY"
tbl_sentences='SENTENCES'
tbl_change="CHANGES"
tbl_lemmata="LEMMATA"
tbl_text="TEXT"
table_names=[tbl_morphology,tbl_sentences,tbl_change,tbl_lemmata,tbl_text]




@app.route('/')
def index():
    isAdmin = session.get('permission','normal')=='admin'
    if isAdmin:
        return redirect('/working/')
    else:
        return redirect('/SENTENCES/')


@app.route('/working/')
def working():
    isLogin,isAdmin = 'username' in session, session.get('permission','normal')=='admin'
    if not isAdmin:
        return redirect('/SENTENCES/')
    dict_working={}
    total_rows = getTotalRowNumber(tbl_morphology)
    min_row=getMinRowNumber(tbl_morphology)
    current_row=request.args.get('row_number') or min_row
    prev_row= request.args.get('from_row') or 0
    try:
        current_row=int(current_row)
        prev_row = int(prev_row)
    except:
        return redirect(url_for('index'))
    if current_row <=0 or current_row>total_rows:
        return redirect(url_for('index'))

     # Morphology
    column_names_morphology=getColumnNames(tbl_morphology)
    formated_col_names_morphology=formatColumn(column_names_morphology)
    if current_row > prev_row:
        data_morphology = g.db.execute('SELECT %s FROM %s WHERE "rowid" >= %s ORDER BY rowid LIMIT 1'%(formated_col_names_morphology, tbl_morphology,current_row)).fetchall()
    else:
        data_morphology = g.db.execute('SELECT %s FROM %s WHERE "rowid" <= %s ORDER BY rowid DESC LIMIT 1'%(formated_col_names_morphology, tbl_morphology,current_row)).fetchall()
    if data_morphology:
        data_morphology=data_morphology[0]
        dict_working['dict_morphology']=dict(zip(column_names_morphology,data_morphology))
        
        
        #Lemmata
        lemmata=dict_working['dict_morphology']['Lemma']
        column_names_lemmata=getColumnNames(tbl_lemmata)
        formated_col_names_lemmata=formatColumn(column_names_lemmata)
        data_lemmata = g.db.execute('SELECT %s FROM %s WHERE "Lemma" = ?'%(formated_col_names_lemmata,tbl_lemmata),[lemmata]).fetchall()
        if data_lemmata:
            dict_working['dict_lemmata']=dict(zip(column_names_lemmata,data_lemmata[0]))
        else:
            dict_working['dict_lemmata']=dict(zip(column_names_lemmata,["" for c in column_names_lemmata]))

        # other words with same headword
        current_rowid = dict_working['dict_morphology']['ID_unique_number']
        other_words_with_lemmata=g.db.execute('SELECT "rowid","Word","SentenceID","Expected_Morph","Analysis" FROM MORPHOLOGY WHERE "Lemma" = ? and "rowid" != ?',[lemmata,current_rowid]).fetchall()
        dict_working['other_words_with_lemmata']=other_words_with_lemmata
        # Changes
        changes=dict_working['dict_morphology']['ID_of_Change']
        column_names_change=getColumnNames(tbl_change)
        test_data=[[i for _ in column_names_change] for i in range(20)]
        dict_working['cols_changes']=column_names_change
        dict_working['data_changes']=test_data

        # Sentences
        sentenceID=dict_working['dict_morphology']['SentenceID']
        column_names_sentences=getColumnNames(tbl_sentences)
        formated_col_names_sentences=formatColumn(column_names_sentences)
        data_sentences = g.db.execute('SELECT %s FROM %s WHERE "SentenceID" = ?'%(formated_col_names_sentences,tbl_sentences),[sentenceID]).fetchall()
        if data_sentences:
            dict_working['dict_sentences']=dict(zip(column_names_sentences,data_sentences[0]))
        else:
            dict_working['dict_sentences']=dict(zip(column_names_sentences,["" for c in column_names_sentences]))
            dict_working['dict_sentences']['SentenceID']=sentenceID

        # other words with same sentenceID
        
        other_words_with_sentenceid=g.db.execute('SELECT "rowid","Word","Lemma","For_Syntax_Tree","PortalRecordNumber" FROM MORPHOLOGY WHERE "SentenceID" = ? and "rowid" != ?',[sentenceID,current_rowid]).fetchall()
        dict_working['other_words_with_sentenceid']=other_words_with_sentenceid

        # row numbers
        # dict_working['total_rows'] = total_rows
        # dict_working['current_row'] = current_rowid
        # global special_characters
        # dict_working['symbols'] = special_characters
        return render_template('index.html',dict_working=dict_working,is_admin=isAdmin,is_login=isLogin,total_rows=total_rows,current_row=current_row,min_row=min_row)
    else:
        return render_template('index.html',dict_working={},is_admin=isAdmin,is_login=isLogin,total_rows=total_rows,current_row=current_row,min_row=min_row)
    

@app.route('/working/update',methods=['POST'])
def working_update():
    isAdmin = session.get('permission','normal')=='admin'
    if not isAdmin:
        return jsonify({'error':"permission error"})
    form_values=request.form
    rowid=form_values['rowid']
    attrs=[k for k in form_values.keys() if k != 'rowid']
    formated_attrs=','.join(['"'+k+'" = ?' for k in attrs])
    values=[form_values[a] for a in attrs]
    # print(attrs)
    # print(formated_attrs)
    # print(values)
    try:
        g.db.execute('update MORPHOLOGY set %s where rowid = %s'%(formated_attrs,rowid),values)
        g.db.commit()
    except Exception as e:
        print(e)
    return redirect('/working/?row_number='+rowid)


@app.route('/working/delete',methods=['POST'])
def working_delete():
    isAdmin = session.get('permission','normal')=='admin'
    if not isAdmin:
        return jsonify({'error':"permission error"})
    form_values=request.form
    rowid=int(form_values['rowid'])
    try:
        g.db.execute('delete from MORPHOLOGY where rowid = ?',[rowid])
        g.db.commit()
    except Exception as e:
        return jsonify({'error':str(e)})
    return jsonify({'success':"Done!"})


@app.route('/new_record/')
def new_record():
    isLogin,isAdmin = 'username' in session, session.get('permission','normal')=='admin'
    if not isLogin:
        return redirect(url_for('user_login'))
    if not isAdmin:
        return redirect('/sentences/')
    not_empty=["Word","Lemma","SentenceID"]
    column_names_morphology=getColumnNames(tbl_morphology)
    column_names_lemmata=getColumnNames(tbl_lemmata)
    column_names_sentences=getColumnNames(tbl_sentences)

    return render_template('new_record.html',
                            cols_morphology=column_names_morphology,
                            cols_lemmata=column_names_lemmata,
                            cols_sentences=column_names_sentences,
                            is_admin=isAdmin,
                            is_login=isLogin,
                            not_empty=not_empty
                            )

@app.route('/new_record/insert',methods=['POST'])
def insert_new_record():
    t_name="MORPHOLOGY"
    form_values=request.form
    print(form_values)
    form_keys=tuple(form_values.keys())
    form_values=tuple(form_values.values())
    formated_cols='('+formatColumn(form_keys)+')'
    placeholders=','.join(['?' for _ in form_values])
    try:
        g.db.execute('insert into %s %s values (%s)'%(t_name,formated_cols,placeholders),form_values)
        g.db.commit()
    except Exception as e:
        return jsonify({'error':str(e)})
    total_rows=getTotalRowNumber(t_name)
    print(total_rows)
    return jsonify({'success':total_rows})




@app.route('/new_record/_query_lemmata')
def query_lemmata():
    a = request.args.get('lemma', '', type=str)
    a = a.strip()
    if a:
        column_names_lemmata=getColumnNames(tbl_lemmata)
        formated_col_names_lemmata=formatColumn(column_names_lemmata)
        data_lemmata = g.db.execute('SELECT %s FROM LEMMATA WHERE "Lemma" = ?'%(formated_col_names_lemmata),[a]).fetchall()
        if data_lemmata:
            lemmata_info=dict(zip(column_names_lemmata,data_lemmata[0]))
            # words_with_this_lamma=g.db.execute('SELECT "Word","SentenceID","Expected_Morph","Analysis" FROM MORPHOLOGY WHERE "Lemma" = ?',[a]).fetchall()
            # words=''
            return jsonify(lemmata_info)
    return jsonify({})

@app.route('/new_record/_query_sentence')
def query_sentences():
    a = request.args.get('sentenceid', '', type=str)
    a = a.strip()
    if a:
        column_names_sentences=getColumnNames(tbl_sentences)
        formated_col_names_sentences=formatColumn(column_names_sentences)
        data_sentences = g.db.execute('SELECT %s FROM SENTENCES WHERE "SentenceID" = ?'%(formated_col_names_sentences),[a]).fetchall()
        if data_sentences:
            d=dict(zip(column_names_sentences,data_sentences[0]))
            print(d)
            return jsonify(d)
    return jsonify({})

@app.route('/<table>/')
def show_table_list(table):
    isLogin,isAdmin = 'username' in session, session.get('permission','normal')=='admin'
    if table.upper() not in table_names:
        return redirect(url_for('index'))
    t_name=table.upper()
    total_rows=getTotalRowNumber(t_name)
    max_page=getMaxPageNum(total_rows,ROWS_PER_PAGE)
    current_page = request.args.get('page', 1)
    
    try:
        current_page=int(current_page)
        if current_page>max_page or current_page<=0:
            current_page=1
    except:
        current_page=1
    target_min_rowid=(current_page-1)*ROWS_PER_PAGE+1
    if t_name == 'MORPHOLOGY':
        column_names_table=['ID_unique_number','Word','Lemma','Expected_Morph','SentenceID','Analysis','Comments','For_Syntax_Tree','PortalRecordNumber']
    elif t_name=='SENTENCES':    
        #ROWID  LATIN_TEXT  LOCUS1  LOCUS2  LOCUS3  SENTENCE    SENTENCEID  SUBUNIT TEXTID  TEXTUAL_NOTES   TRANSLATION TRANSLATION_NOTES   VARIANT_READINGS
        column_names_table=['ID_unique_number','TextID','SentenceID','Sentence','Latin_Text','Locus1','Translation','Translation_Note','Variant_Readings']
    else:
        column_names_table=getColumnNames(t_name)
    formated_col_names_table=formatColumn(column_names_table)
    table_data=g.db.execute('SELECT %s FROM %s WHERE rowid >= %s ORDER BY rowid limit %s'%(formated_col_names_table,t_name,target_min_rowid,ROWS_PER_PAGE)).fetchall()
    return render_template('table_content.html',
                            table_name=t_name,
                            other_tables=[t for t in table_names if t != t_name],
                            tr_ths=['rowid']+column_names_table[1:],
                            table_data=table_data,
                            max_page=max_page,
                            current_page=current_page,
                            is_login=isLogin,
                            is_admin=isAdmin)

@app.route('/<table>/<row_id>/')
def show_table_detail(table,row_id):
    isLogin,isAdmin = 'username' in session, session.get('permission','normal')=='admin'
    words_with_lemmata=[]

    innerHTML,data={},{}
    
    t_name=table.upper()
    if t_name not in table_names:
        return redirect('/')
    s=''
    try:
        rowid=int(row_id)
    except:
        return redirect('/')
    column_names_table=getColumnNames(t_name)
    formated_col_names_table=formatColumn(column_names_table)
    total_rows=getTotalRowNumber(t_name)
    if t_name=="SENTENCES":
        table_detail=g.db.execute('select %s from %s where rowid = %s limit 1'%(formated_col_names_table,t_name,rowid)).fetchall()
        if table_detail:
            sentence_dict=dict(zip(column_names_table,table_detail[0]))
            print(sentence_dict)
            sentenceid=sentence_dict['SentenceID']
            sentence=sentence_dict['Sentence']
            words=dict(g.db.execute('select "Word",rowid from %s where "SentenceID" = ?'%(tbl_morphology),[sentenceid] ).fetchall())

            sentence=sentence.replace(';','; ').replace(';','; ')+'.' # first ';' and second ';' are different!!!  
            if sentence[-1]=='.':
                sentence=sentence[:-1]
            words_in_sentence=sentence.split()
            print(words_in_sentence)
            def formatATag(s,i):
                return '<a class="href_td" href="/MORPHOLOGY/%s/">%s</a>'%(i,s)
            s=[]
            for word in words_in_sentence:
                if word in words:
                    s.append(formatATag(word,words[word]))
                elif word.rstrip('.') in words:
                    s.append(formatATag(word.rstrip('.'),words[word.rstrip('.')])+'.')
                elif word.rstrip(';') in words:
                    s.append(formatATag(word.rstrip(';'),words[word.rstrip(';')])+';')
                elif word.rstrip(';') in words:
                    s.append(formatATag(word.rstrip(';'),words[word.rstrip(';')])+';')
                else:
                    s.append(word)
            s='&nbsp;'.join(s)
            innerHTML={"Sentence":s}
            textid=g.db.execute('select "TextID" from %s where rowid = %s limit 1'%(t_name,rowid)).fetchall()[0][0]
            text_rowid=g.db.execute('select rowid from "TEXT" where "Text_ID" = ? limit 1',[textid]).fetchall()[0][0]
            innerHTML["TextID"]='<a class="href_td" href="/TEXT/%s/">%s</a>'%(text_rowid,textid)

            data=dict(zip(column_names_table,table_detail[0]))

        
    elif t_name == "MORPHOLOGY":
        table_detail=g.db.execute('select %s from %s where rowid == %s limit 1'%(formated_col_names_table,t_name,rowid) ).fetchall()
        if table_detail:
            table_detail=table_detail[0]
            data=dict(zip(column_names_table,table_detail))
            lemmata = data["Lemma"]
            sentenceid = data["SentenceID"]
            lemmata_id=g.db.execute('select rowid from LEMMATA where "Lemma" = ? limit 1',(lemmata,)).fetchall()
            sentence_id=g.db.execute('select rowid from SENTENCES where "SentenceID" = ? limit 1',(sentenceid,)).fetchall()
            if lemmata_id:
                lemmata_id=lemmata_id[0][0]
                innerHTML["Lemma"]='<a class="href_td" href="/LEMMATA/%s/">%s</a>'%(lemmata_id,lemmata)
            if sentence_id:
                sentence_id=sentence_id[0][0]
                innerHTML["SentenceID"]='<a class="href_td" href="/SENTENCES/%s/">%s</a>'%(sentence_id,sentenceid)

    elif t_name == "LEMMATA":
        table_detail=g.db.execute('select %s from %s where rowid == %s limit 1'%(formated_col_names_table,t_name,rowid) ).fetchall()
        if table_detail:
            table_detail=table_detail[0]
            data=dict(zip(column_names_table,table_detail))
            lemmata=data['Lemma']
            words_with_lemmata=g.db.execute('SELECT "rowid","Word","SentenceID","Expected_Morph","Analysis" FROM MORPHOLOGY WHERE "Lemma" = ?',[lemmata]).fetchall()
    else:
        table_detail=g.db.execute('select %s from %s where rowid == %s limit 1'%(formated_col_names_table,t_name,rowid) ).fetchall()
        print(table_detail)
        if table_detail:
            table_detail=table_detail[0]
            data=dict(zip(column_names_table,table_detail))
    return render_template('table_detail.html',
                                table_name=t_name,
                                other_tables=[t for t in table_names if t != t_name],
                                is_login=isLogin,
                                is_admin=isAdmin,
                                data=data,
                                innerHTML=innerHTML,
                                total_rows=total_rows,
                                current_rowid=rowid,
                                words_with_lemmata=words_with_lemmata
                                )

@app.route('/<table>/update/',methods=['POST'])
def table_update(table):
    print(request.form)
    rowid=int(request.form['rowid'])
    t_name=table.upper()
    column_names_table=getColumnNames(t_name)
    data=g.db.execute('SELECT %s from %s where "rowid" = ? limit 1'%(formatColumn(column_names_table),t_name),[rowid]).fetchall()[0]
    return render_template('table_detail_update.html',
                        table_name=t_name,
                        other_tables=[t for t in table_names if t != t_name],
                        data=dict(zip(column_names_table,data))
                        )

@app.route('/<table>/update/update',methods=['POST'])
def table_update_confirmed(table):
    isAdmin = session.get('permission','normal')=='admin'
    if not isAdmin:
        return jsonify({'error':"permission error"})
    t_name=table.upper()
    form_values=request.form
    # print(form_values)
    rowid=int(form_values['rowid'])
    keys= [k for k in form_values.keys() if k != 'rowid']
    values=[]
    formated_key=[]
    for k in keys:
        values.append(form_values[k])
        formated_key.append('"'+k+'"'+' = ?')
    print('update %s set %s where rowid = %s'%(t_name,','.join(formated_key),rowid))
    try:
        g.db.execute('update %s set %s where rowid = %s'%(t_name,','.join(formated_key),rowid),values)
        g.db.commit()
    except Exception as e:
        return jsonify({'error':str(e)})
    return jsonify({'success':rowid})

@app.route('/<table>/update/delete',methods=['POST'])
def table_delete_confirmed(table):
    isAdmin = session.get('permission','normal')=='admin'
    if not isAdmin:
        return jsonify({'error':"permission error"})
    t_name=table.upper()
    form_values=request.form
    rowid=int(form_values['rowid'])
    try:
        g.db.execute('delete from %s where rowid = %s'%(t_name,rowid))
        g.db.commit()
    except Exception as e:
        return jsonify({'error':str(e)})
    return jsonify({'success':"Done!"})

@app.route('/<table>/add_new/',methods=['GET'])
def table_add_new(table):
    isLogin,isAdmin = 'username' in session, session.get('permission','normal')=='admin'
    t_name=table.upper()
    next_sentenceID,non_empty,column_names=None,[],[]
    if t_name not in table_names:
        return redirect('/SENTENCES/')
    if t_name=="SENTENCES":
        next_sentenceID=getNextSentenceID()
        column_names=getColumnNames(t_name)
        non_empty=['SentenceID','TextID']
    elif t_name=="MORPHOLOGY":
        return redirect('/new_record/')
    else:
        column_names=getColumnNames(t_name)


    return render_template('table_add_new.html',
                                table_name=t_name,
                                other_tables=[t for t in table_names if t != t_name],
                                is_login=isLogin,
                                is_admin=isAdmin,
                                next_sentenceID=next_sentenceID,
                                column_names=column_names,
                                non_empty=non_empty)

@app.route('/<table>/add_new/insert',methods=['POST'])
def table_insert(table):
    t_name=table.upper()
    if t_name not in table_names:
        return jsonify({})
    form_values=request.form
    form_keys=tuple(form_values.keys())
    form_values=tuple(form_values.values())
    formated_cols='('+formatColumn(form_keys)+')'
    placeholders=','.join(['?' for _ in form_values])
    try:
        g.db.execute('insert into %s %s values (%s)'%(t_name,formated_cols,placeholders),form_values)
        g.db.commit()
    except Exception as e:
        return jsonify({'error':str(e)})
    print(formated_cols)
    print(form_values,placeholders)
    total_rows=getTotalRowNumber(t_name)
    return jsonify({'success':total_rows})

@app.route('/test/')
def add_test():
    return render_template('test.html')


@app.route('/testjs/')
def testJson():
    a={"a":"1","b":{'1':"a",'2':'B'}}
    a={"a":["1",'2','3']}
    return jsonify(a)
    

@app.route('/sql/',methods=['GET'])
def sql_page():
    table_info=g.db.execute('select name,sql from sqlite_master where type = \'table\'').fetchall()
    return render_template('sql.html',tables=table_names,table_info=table_info)

@app.route("/downloadsqlite",methods=['GET'])
def downloadSqlite():
    path='working.sqlite3'
    return send_file(path, as_attachment=True)

@app.route('/result/',methods=['POST'])
def sql_result():
    sql_sentence=request.form['sql']
    print("POST Form values: ",sql_sentence)
    data,error,t_heads,title=[],None,[],'No record found'
    try:
        data=g.db.execute(sql_sentence).fetchall()[:1000]
    except Exception as e:
        error=str(e).upper()
    if data:
        t_heads=list(range(len(data[0])))
        title="%s record found (max 1000)"%(len(data))
    
    return render_template('sql_result.html',
                            tables=table_names,
                            data=data,
                            error=error,
                            sql=sql_sentence,
                            t_heads=t_heads,
                            title=title)

@app.route('/login/',methods=['GET','POST'])
def user_login():
    if request.method == 'GET':
        if 'username' in session:
            return redirect('/')
        return render_template('login.html')
    else:
        print('post')
        form_values=request.form
        username=str(form_values['username'])
        password=str(form_values['password'])
        user_attrs = g.user_db.execute('PRAGMA table_info(USER)').fetchall()
        user_attrs = [d[1] for d in user_attrs if d[1]!='password']
        formated_user_attrs=formatColumn(user_attrs)
        hashed_password=hashlib.md5(password.encode()).hexdigest()
        user_data=g.user_db.execute('SELECT %s FROM USER WHERE "username"=? and "password"=?'%(formated_user_attrs),[username,hashed_password]).fetchall()
        print(user_data,user_attrs)
        if user_data:
            for i in range(len(user_attrs)):
                session[user_attrs[i]]=user_data[0][i]
            return jsonify({})
        return jsonify({'error':'wrong username or password'})

@app.route('/logout/',methods=['POST'])
def user_logout():
    session.clear()
    return jsonify({})



def getCurrentMaxSentenceID():
    return g.db.execute('select SentenceID from SENTENCES order by cast(substr(SentenceID,7) as integer) desc limit 1').fetchall()[0][0]

def getNextSentenceID():
    current_id=getCurrentMaxSentenceID()
    prefix = current_id[0:6]
    suffix = current_id[6:]
    nextValue = str(int(suffix)+1)
    return prefix+nextValue

def getMaxPageNum(total_rows, per_page):
    pages=int(math.ceil(total_rows/per_page))
    if pages<=0:
        return 1
    return pages


def escapeSpecialStr(str_o):
    # .replace('/','//').replace('[','/[').replace(']','/]').replace('%','/%').replace('&','/&').replace('_','/_').replace('(','/(').replace(')','/)').replace('"','/"')
    return str_o.replace("'","''")

def connect_db():
    isAdmin=session.get('permission','normal')=='admin'
    if isAdmin:
        return sqlite3.connect('working.sqlite3'),sqlite3.connect('user.sqlite3')
    else:
        # abs_path=os.path.abspath('working.sqlite3')
        abs_path=os.path.dirname(os.path.realpath('working.sqlite3'))
        uri_abs_path="file://"+abs_path+'?mode=ro'
        return sqlite3.connect(uri_abs_path,uri=True),sqlite3.connect('user.sqlite3')
        # return sqlite3.connect('file://working.sqlite3?mode=ro',uri=True),sqlite3.connect('user.sqlite3')

@app.before_request
def before_request():
    g.db,g.user_db = connect_db()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()
    if hasattr(g, 'user_db'):
        g.user_db.close()

def getColumnNames(table_name):
    info = g.db.execute('PRAGMA table_info(%s)'%(table_name)).fetchall()
    info = [inf[1] for inf in info]
    #make sure the first element is always "ID_unique_number"
    temp_info = [i for i in info if i.lower() != "id_unique_number"]
    return ["ID_unique_number"]+temp_info



def getTotalRowNumber(table_name):
    rows=g.db.execute('SELECT rowid FROM %s ORDER BY rowid DESC LIMIT 1'%(table_name)).fetchall()
    if len(rows)==0:
        return 0
    return int(rows[0][0])

def getMinRowNumber(table_name):
    rows=g.db.execute('SELECT rowid FROM %s ORDER BY rowid ASC LIMIT 1'%(table_name)).fetchall()
    if len(rows)==0:
        return 1
    return int(rows[0][0])

def queryDB(formated_col_names, table_name, limit=1, start_index=0):
    data=g.db.execute('SELECT %s FROM %s LIMIT %s OFFSET %s'%(formated_col_names, table_name, limit, start_index)).fetchall()
    return data


def formatColumn(column):
    c=['"%s"'%(col) for col in column]
    return ','.join(c)



#
# Script options.
#

def get_option_parser():
    parser = optparse.OptionParser()
    parser.add_option(
        '-p',
        '--port',
        default=8010,
        help='Port for web interface, default=8080',
        type='int')
    parser.add_option(
        '-H',
        '--host',
        default='127.0.0.1',
        help='Host for web interface, default=127.0.0.1')
    parser.add_option(
        '-d',
        '--debug',
        action='store_true',
        help='Run server in debug mode')
    parser.add_option(
        '-x',
        '--no-browser',
        action='store_false',
        default=True,
        dest='browser',
        help='Do not automatically open browser page.')
    return parser

def die(msg, exit_code=1):
    sys.stderr.write('%s\n' % msg)
    sys.stderr.flush()
    sys.exit(exit_code)

def open_browser_tab(host, port):

    url = 'http://%s:%s/' % (host, port)

    def _open_tab(url):
        time.sleep(1)
        webbrowser.open_new_tab(url)

    thread = threading.Thread(target=_open_tab, args=(url,))
    thread.daemon = True
    thread.start()

def main():
    # This function exists to act as a console script entry-point.
    from werkzeug.contrib.fixers import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    parser = get_option_parser()
    options, args = parser.parse_args()

    
    if options.browser:
        import socket
        myname = socket.getfqdn(socket.gethostname())
        myaddr = socket.gethostbyname(myname)
        open_browser_tab(myaddr, 8010)
    app.run(host='0.0.0.0', port=8010, debug=True,threaded = True)


if __name__ == '__main__':
    main()
