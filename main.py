from xbmcswift2 import Plugin
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import base64
import os,os.path,stat
import urllib,urllib2,urlparse
import time,datetime
#datetime.datetime.strptime("2016", "%Y")
import threading
import json
import subprocess
import sqlite3
import collections
import socket
from rpc import RPC
import threading


ADDON = xbmcaddon.Addon()

plugin = Plugin()


def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')

def log(v):
    xbmc.log(repr(("[plugin.video.addon.recorder]",v)),xbmc.LOGERROR)

#log(sys.argv)

def get_icon_path(icon_name):
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_id(),icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(),icon_name)

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

def escape( str ):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str

def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    return str

def delete(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        xbmcvfs.delete(path+file)
    for dir in dirs:
        delete(path + dir + '/')
    xbmcvfs.rmdir(path)


@plugin.route('/get_settings')
def get_settings():
    plugin.open_settings()

@plugin.route('/add_search_folder/<path>/<label>')
def add_search_folder(path,label):
    folders = plugin.get_storage('folders')
    folders[path] = label


@plugin.route('/remove_search_folder/<path>')
def remove_search_folder(path):
    folders = plugin.get_storage('folders')
    if path in folders:
        del folders[path]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_rule/<path>/<label>/<name>')
def add_rule(path,label,name):
    if name == "EVERYTHING":
        regex = ".*"
    else:
        regex = re.escape(name)
    dialog = xbmcgui.Dialog()
    regex = dialog.input('Regex (%s)' % name, regex)
    if regex:
        regexes = plugin.get_storage('regexes')
        regexes[(regex,path)] = label


@plugin.route('/remove_rule/<regex>/<path>')
def remove_rule(regex,path):
    regexes = plugin.get_storage('regexes')
    if (regex,path) in regexes:
        del regexes[(regex,path)]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_renamer/<regex>/<path>')
def remove_renamer(regex,path):
    renamers = plugin.get_storage('renamers')
    if (regex,path) in renamers:
        del renamers[(regex,path)]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/renamer/<regex>/<path>')
def renamer(regex,path):
    renamers = plugin.get_storage('renamers')
    from_regex = regex
    to_regex = regex
    if (regex,path) in renamers:
        from_regex,to_regex = json.loads(renamers[(regex,path)])
    dialog = xbmcgui.Dialog()
    from_regex = dialog.input('Enter Find Regex (%s)' % regex, from_regex)
    #log(from_regex)
    if from_regex:
        to_regex = dialog.input('Enter Replace Regex (%s)' % regex, to_regex)
        if to_regex:
            renamers[(regex,path)] = json.dumps((from_regex,to_regex))


@plugin.route('/rules')
def rules():
    regexes = plugin.get_storage('regexes')
    renamers = plugin.get_storage('renamers')
    items = []
    for (regex,path),label in regexes.iteritems():
        #log((regex,path))
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_rule, regex=regex.encode("utf8"),path=path))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Renamer', 'XBMC.RunPlugin(%s)' % (plugin.url_for(renamer, regex=regex.encode("utf8"),path=path))))
        if (regex,path) in renamers:
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Renamer', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_renamer, regex=regex.encode("utf8"),path=path))))
        items.append({
            "label" : "{} [{}]".format(regex,label),
            "path" : path,
            "thumbnail" : get_icon_path('search'),
            'context_menu': context_items,
        })

    return items


@plugin.route('/service')
def service():

    #log("service")
    thread = threading.Thread(target=service_thread)
    thread.daemon = True
    thread.start()



@plugin.route('/service_thread')
def service_thread():
    xbmcgui.Dialog().notification("Addon Recorder","starting",sound=False)
    recordings = plugin.get_storage('recordings')

    #log("service_thread")
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    regexes = plugin.get_storage('regexes')
    renamers = plugin.get_storage('renamers')
    items = []
    for (regex,path),label in regexes.iteritems():
        #log((regex,path))
        media = "video"
        try:
            response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
            #log(response)
        except:
            return
        files = response["files"]
        dir_items = []
        file_items = []
        for f in files:
            original_label = f['label']

            #log(original_label)
            #log(recordings.values())
            #if original_label in recordings.values():
                #log(("already recorded",original_label))
                #continue

            search_label = remove_formatting(original_label)
            url = f['file']
            thumbnail = f['thumbnail']
            if f['filetype'] == 'file':
                #log(("found",label))
                if not re.search(regex,search_label):
                    continue
                log(("record",url))
                #continue

                if (regex,path) in renamers:
                    from_regex,to_regex = json.loads(renamers[(regex,path)])
                    record_label = re.sub(from_regex,to_regex,original_label)
                else:
                    record_label = "[%s] %s" % (label,original_label)

                if record_label not in recordings.values():
                    record_thread(url,record_label)


    #log("finished")
    xbmcgui.Dialog().notification("Addon Recorder","finished",sound=False)


@plugin.route('/record/<url>/<label>')
def record(url,label):
    thread = threading.Thread(target=record_thread,args=[url,label])
    thread.daemon = True
    thread.start()


def record_thread(url,label):

    #log(("record",url,label))
    recordings = plugin.get_storage('recordings')

    original_label = label
    if not url.startswith('http'):
        player = xbmc.Player()
        #log(("play",url))
        player.play(url)
        #xbmc.executebuiltin('PlayMedia(%s)' % url)
        count = 60
        url = ""
        while count:
            count = count - 1
            time.sleep(1)
            if player.isPlaying():
                url = player.getPlayingFile()
                break
        time.sleep(1)
        player.stop()
        time.sleep(1)
    if not url:
        return
    #log(("record",url))
    if url in recordings:
        log(("already recorded",label,url))
        #return

    url_headers = url.split('|', 1)
    url = url_headers[0]
    headers = {}
    if len(url_headers) == 2:
        sheaders = url_headers[1]
        aheaders = sheaders.split('&')
        if aheaders:
            for h in aheaders:
                k, v = h.split('=', 1)
                headers[k] = urllib.unquote_plus(v)

    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    cmd = [ffmpeg]
    for h in headers:
        cmd.append("-headers")
        cmd.append("%s:%s" % (h, headers[h]))
    cmd.append("-i")
    cmd.append(url)

    '''
    if (regex,path) in renamers:
        from_regex,to_regex = json.loads(renamers[(regex,path)])
        label = re.sub(from_regex,to_regex,label)
    '''

    filename = re.sub(r"[^\w' \[\]-]+", "", label, flags=re.UNICODE)
    recording_path = plugin.get_setting("download") + filename + ' ' + datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S') +'.ts'
    log(("filename",recording_path))

    seconds = 60*60*4
    cmd = cmd + ["-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "300", "-y", "-t", str(seconds), "-c", "copy"]
    cmd = cmd + ['-f', 'mpegts','-']
    log(("start",cmd))

    recordings[url] = original_label
    recordings.sync()
    xbmcgui.Dialog().notification("Addon Recorder starting",original_label,sound=False)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=windows())
    video = xbmcvfs.File(recording_path,'wb')
    while True:
        data = p.stdout.read(1000000)
        if not data:
            break
        video.write(data)
    video.close()
    #stdout.close()
    p.wait()
    log(("done",cmd))
    xbmcgui.Dialog().notification("Addon Recorder finished",original_label,sound=False)



@plugin.route('/links')
def links():
    return find_links()

@plugin.cached(TTL=plugin.get_setting('ttl',int))
def find_links():
    recordings = plugin.get_storage('recordings')

    items = []

    regexes = plugin.get_storage('regexes')
    renamers = plugin.get_storage('renamers')
    items = []
    for (regex,path),label in regexes.iteritems():
        #log((regex,path))
        media = "video"
        try:
            response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
            #log(response)
        except:
            return
        files = response["files"]
        dir_items = []
        file_items = []
        for f in files:
            original_label = f['label']

            search_label = remove_formatting(original_label)
            url = f['file']
            thumbnail = f['thumbnail']
            if f['filetype'] == 'file':
                #log(("found",label))
                if not re.search(regex,search_label):
                    continue
                if (regex,path) in renamers:
                    from_regex,to_regex = json.loads(renamers[(regex,path)])
                    record_label = re.sub(from_regex,to_regex,original_label)
                else:
                    record_label = "[%s] %s" % (label,original_label)

                if record_label in recordings.values():
                    recorded = True
                else:
                    recorded = False

                #label = "[{}] {}".format(path_label,label)
                #log(("add",label))
                context_items = []
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record, url=url, label=record_label.encode("utf8")))))
                if recorded:
                    record_label = "[COLOR yellow]%s[/COLOR]" % record_label

                items.append({
                    'label': record_label,
                    'path': url,
                    'thumbnail': f['thumbnail'],
                    'context_menu': context_items,
                    'is_playable': True,
                    'info_type': 'Video',
                    'info':{"mediatype": "episode", "title": label}
                })
    return items


@plugin.route('/search_dialog')
def search_dialog():
    searches = plugin.get_storage("searches")
    what = xbmcgui.Dialog().input("Search","")
    if what:
        searches[what] = None
        return search(what)


@plugin.route('/choose_search_folders/<what>')
def choose_search_folders(what):
    searches = plugin.get_storage("searches")
    folders = plugin.get_storage('folders')
    folder_labels = [(k,folders[k]) for k in sorted(folders,key=lambda k:folders[k])]
    labels = [i[1] for i in folder_labels]
    indexes = xbmcgui.Dialog().multiselect("Search",labels)
    if indexes != None:
        paths = [folder_labels[i][0] for i in indexes]
        searches[what] = json.dumps(paths)
        #return search(what)
    else:
        if what in searches:
            searches[what] = None


@plugin.route('/remove_search/<what>')
def remove_search(what):
    searches = plugin.get_storage("searches")
    if what in searches:
        del searches[what]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/search_directory')
def search_directory():
    searches = plugin.get_storage("searches")
    items = []
    items.append({
        "label": "New Search",
        "path": plugin.url_for('search_dialog'),
        'thumbnail': get_icon_path('search'),
    })
    for search in searches:
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Search', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_search, what=search.encode("utf8")))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Choose Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for(choose_search_folders, what=search.encode("utf8")))))
        items.append({
            "label": search,
            "path": plugin.url_for('search',what=search),
            'thumbnail': get_icon_path('search'),
            'context_menu': context_items,
        })
    return items



@plugin.route('/search/<what>')
def search(what):
    return search_folders(what)


@plugin.cached(TTL=plugin.get_setting('ttl',int))
def search_folders(what):
    search_paths = None
    searches = plugin.get_storage("searches")
    if what in searches:
        if searches[what] != None:
            search_paths = json.loads(searches[what])
    recordings = plugin.get_storage('recordings')
    folders = plugin.get_storage('folders')

    items = []
    dir_items = []
    file_items = []
    for path,label in folders.iteritems():
        if search_paths and path not in search_paths:
            continue
        media = "video"
        try:
            response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
            #log(response)
        except:
            return
        files = response["files"]

        for f in files:
            original_label = f['label']

            search_label = remove_formatting(original_label)
            url = f['file']
            thumbnail = f['thumbnail']

            if not re.search(what,search_label,flags=re.I):
                continue

            if f['filetype'] == 'directory':

                file_label = search_label
                context_items = []
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=url, label=file_label.encode("utf8"), name="EVERYTHING"))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_folder, path=url, label=file_label.encode("utf8")))))
                dir_label = "[B]%s[/B]" % file_label
                if url in folders:
                    dir_label = "[COLOR yellow]%s[/COLOR]" % dir_label
                    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Search', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_search_folder, path=url))))
                else:
                    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add to Search', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_search_folder, path=url, label=file_label.encode("utf8")))))
                dir_items.append({
                    'label': dir_label,
                    'path': plugin.url_for('folder', path=url, label=file_label.encode("utf8")),
                    'thumbnail': f['thumbnail'],
                    'context_menu': context_items,
                })

            elif f['filetype'] == 'file':

                record_label = "[%s] %s" % (label,original_label)

                if record_label in recordings.values():
                    recorded = True
                else:
                    recorded = False

                #label = "[{}] {}".format(path_label,label)
                #log(("add",label))
                context_items = []
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record, url=url, label=record_label.encode("utf8")))))
                if recorded:
                    record_label = "[COLOR yellow]%s[/COLOR]" % record_label

                file_items.append({
                    'label': record_label,
                    'path': url,
                    'thumbnail': f['thumbnail'],
                    'context_menu': context_items,
                    'is_playable': True,
                    'info_type': 'Video',
                    'info':{"mediatype": "episode", "title": label}
                })

    return dir_items + file_items


def windows():
    if os.name == 'nt':
        return True
    else:
        return False


def android_get_current_appid():
    with open("/proc/%d/cmdline" % os.getpid()) as fp:
        return fp.read().rstrip("\0")


@plugin.route('/delete_ffmpeg')
def delete_ffmpeg():
    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()
        xbmcvfs.delete(ffmpeg_dst)


def ffmpeg_location():
    ffmpeg_src = xbmc.translatePath(plugin.get_setting('ffmpeg'))

    if xbmc.getCondVisibility('system.platform.android'):
        ffmpeg_dst = '/data/data/%s/ffmpeg' % android_get_current_appid()

        if (plugin.get_setting('ffmpeg') != plugin.get_setting('ffmpeg.last')) or (not xbmcvfs.exists(ffmpeg_dst) and ffmpeg_src != ffmpeg_dst):
            xbmcvfs.copy(ffmpeg_src, ffmpeg_dst)
            plugin.set_setting('ffmpeg.last',plugin.get_setting('ffmpeg'))

        ffmpeg = ffmpeg_dst
    else:
        ffmpeg = ffmpeg_src

    if ffmpeg:
        try:
            st = os.stat(ffmpeg)
            if not (st.st_mode & stat.S_IXUSR):
                try:
                    os.chmod(ffmpeg, st.st_mode | stat.S_IXUSR)
                except:
                    pass
        except:
            pass
    if xbmcvfs.exists(ffmpeg):
        return ffmpeg
    else:
        xbmcgui.Dialog().notification("Addon Recorder", "ffmpeg exe not found!")


@plugin.route('/record_folder/<path>/<label>')
def record_folder(path,label):
    items = folder(path,label)
    items = [i for i in items if i.get("is_playable")]
    labels = [i["label"] for i in items]
    indexes = xbmcgui.Dialog().multiselect(label,labels)
    if indexes == None:
        return
    if not len(indexes):
        indexes = range(len(items))
    if indexes:
        for index in indexes:
            url = items[index]["path"]
            item_label = items[index]["label"]
            record_label = "[%s] %s" % (label,item_label)
            #log((record_label,url))
            record_thread(url,record_label)


@plugin.route('/folder/<path>/<label>')
def folder(path,label):
    label = label.decode("utf8")
    #log(path)
    folders = plugin.get_storage('folders')
    media = "video"
    try:
        response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
        #log(response)
    except:
        return
    files = response["files"]
    dir_items = []
    file_items = []
    for f in files:
        file_label = remove_formatting(f['label'])
        url = f['file']
        thumbnail = f['thumbnail']
        if not thumbnail:
            thumbnail = get_icon_path('unknown')
        context_items = []
        if f['filetype'] == 'directory':
            if media == "video":
                window = "10025"
            elif media in ["music","audio"]:
                window = "10502"
            else:
                window = "10001"

            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=url, label=file_label.encode("utf8"), name="EVERYTHING"))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_folder, path=url, label=file_label.encode("utf8")))))
            dir_label = "[B]%s[/B]" % file_label
            if url in folders:
                dir_label = "[COLOR yellow]%s[/COLOR]" % dir_label
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Search', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_search_folder, path=url))))
            else:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add to Search', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_search_folder, path=url, label=file_label.encode("utf8")))))
            dir_items.append({
                'label': dir_label,
                'path': plugin.url_for('folder', path=url, label=file_label.encode("utf8")),
                'thumbnail': f['thumbnail'],
                'context_menu': context_items,
            })
        else:
            record_label = "[%s] %s" % (label,file_label)
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=path, label=label.encode("utf8"), name=file_label.encode("utf8")))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record, url=url, label=record_label.encode("utf8")))))
            file_items.append({
                'label': "%s" % file_label,
                #'path': plugin.url_for('record', path=url, label=label.encode("utf8"), name=file_label.encode("utf8")),
                'path': url,
                'thumbnail': f['thumbnail'],
                'context_menu': context_items,
                'is_playable': True,
                'info_type': 'Video',
                'info':{"mediatype": "episode", "title": file_label}
            })
    return sorted(dir_items, key=lambda x: x["label"].lower()) + sorted(file_items, key=lambda x: x["label"].lower())


@plugin.route('/clear_all_recordings')
def clear_all_recordings():
    recordings = plugin.get_storage('recordings')
    recordings.clear()


@plugin.route('/clear_recordings')
def clear_recordings():
    recordings = plugin.get_storage('recordings')

    recordings_labels = [(k,v) for k,v in sorted(recordings.iteritems(),key=lambda x: x[1])]
    labels = [x[1] for x in recordings_labels]

    indexes = xbmcgui.Dialog().multiselect("Clear recordings",labels)
    if indexes:
        for index in indexes:
            url = recordings_labels[index][0]
            del recordings[url]

@plugin.route('/clear_folders')
def clear_folders():
    folders = plugin.get_storage('folders')

    folders_labels = [(k,v) for k,v in sorted(folders.iteritems(),key=lambda x: x[1])]
    labels = [x[1] for x in folders_labels]

    indexes = xbmcgui.Dialog().multiselect("Clear folders",labels)
    if indexes:
        for index in indexes:
            url = folders_labels[index][0]
            del folders[url]


@plugin.route('/browse/<table>')
def browse(table):
    conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/%s/replay.db' % addon_id()), detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS %s (title TEXT, file TEXT, date TIMESTAMP, PRIMARY KEY(date))' % table)
    items = []
    for row in c.execute('SELECT DISTINCT title,file FROM %s ORDER BY date DESC' % table):
        (title,file)   = row
        #log((title,year,file,link))
        if not title or (title == ".."):
            continue
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record, label=title.encode("utf8"), url=file))))
        title = re.sub('\[.*?\]','',title)
        if plugin.get_setting('url') == 'true':
            label = "%s [COLOR dimgray][%s][/COLOR]" % (title,file)
        else:
            label = title
        items.append(
        {
            'label': label,
            'path': file,#plugin.url_for('select', title=title,year=year),
            'thumbnail':get_icon_path('files'),
            'is_playable': True,
            'info_type': 'Video',
            'info':{"mediatype": "movie", "title": label},
            'context_menu': context_items,
        })
    conn.commit()
    conn.close()
    return items


@plugin.route('/clear_database')
def clear_database():
    conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/%s/replay.db' % addon_id()), detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute('DROP TABLE streams')
    c.execute('DROP TABLE links')
    c.execute('CREATE TABLE IF NOT EXISTS streams (title TEXT, file TEXT, date TIMESTAMP, PRIMARY KEY(file))')
    c.execute('CREATE TABLE IF NOT EXISTS links (title TEXT, file TEXT, date TIMESTAMP, PRIMARY KEY(file))')
    conn.commit()
    conn.close()

@plugin.route('/')
def index():
    items = []
    context_items = []

    items.append(
    {
        'label': "Library",
        'path': plugin.url_for('folder',path="library://video",label="Library"),
        'thumbnail':get_icon_path('movies'),
        'context_menu': context_items,
    })

    items.append(
    {
        'label': "Rules",
        'path': plugin.url_for('rules'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })

    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear Recordings', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_recordings))))
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear All Recordings', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_all_recordings))))
    items.append(
    {
        'label': "Recordings",
        'path': plugin.get_setting('download'),
        'thumbnail':get_icon_path('recordings'),
        'context_menu': context_items,
    })
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear Last Played', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_database))))
    items.append(
    {
        'label': "Found Links",
        'path': plugin.url_for('links'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })
    items.append(
    {
        'label': "Last Played",
        'path': plugin.url_for('browse',table='links'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })
    items.append(
    {
        'label': "Record",
        'path': plugin.url_for('service'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear Search Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_folders))))
    items.append(
    {
        'label': "Search",
        'path': plugin.url_for('search_directory'),
        'thumbnail':get_icon_path('search'),
        'context_menu': context_items,
    })
    '''
    items.append(
    {
        'label': "Open Settings",
        'path': plugin.url_for('get_settings'),
        'thumbnail':get_icon_path('settings'),
        'context_menu': context_items,
    })
    '''
    return items


if __name__ == '__main__':
    plugin.run()

