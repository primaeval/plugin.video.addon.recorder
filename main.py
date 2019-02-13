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
    label = re.sub(r"\[/?[BI]\]",'',label,flags=re.I)
    label = re.sub(r"\[/?COLOR.*?\]",'',label,flags=re.I)
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


@plugin.route('/add_favourite_folder/<path>/<label>')
def add_favourite_folder(path,label):
    favourites = plugin.get_storage('favourites')
    label = xbmcgui.Dialog().input("Add Favourite: \"%s\"\n%s" % (label,path),label)
    if label:
        favourites[path] = label
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_favourite_folder/<path>')
def remove_favourite_folder(path):
    favourites = plugin.get_storage('favourites')
    if path in favourites:
        del favourites[path]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_trakt_movie_folder/<path>/<label>')
def add_trakt_movie_folder(path,label):
    trakt_movies = plugin.get_storage('trakt_movies')
    label = xbmcgui.Dialog().input("Add trakt_movie: \"%s\"\n%s" % (label,path),label)
    if label:
        trakt_movies[path] = label
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_trakt_movie_folder/<path>')
def remove_trakt_movie_folder(path):
    trakt_movies = plugin.get_storage('trakt_movies')
    if path in trakt_movies:
        del trakt_movies[path]
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/add_trakt_shows_folder/<path>/<label>')
def add_trakt_shows_folder(path,label):
    trakt_shows = plugin.get_storage('trakt_shows')
    label = xbmcgui.Dialog().input("Add trakt_shows: \"%s\"\n%s" % (label,path),label)
    if label:
        trakt_shows[path] = label
        xbmc.executebuiltin('Container.Refresh')


@plugin.route('/remove_trakt_shows_folder/<path>')
def remove_trakt_shows_folder(path):
    trakt_shows = plugin.get_storage('trakt_shows')
    if path in trakt_shows:
        del trakt_shows[path]
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



@plugin.route('/rules')
def rules():
    regexes = plugin.get_storage('regexes')
    items = []
    for (regex,path),label in regexes.iteritems():
        #log((regex,path))
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_rule, regex=regex.encode("utf8"),path=path.encode("utf8")))))
        if path.startswith('plugin://'):
            addon = re.search('plugin://(.*?)/',path+'/').group(1)
            thumbnail = xbmcaddon.Addon(addon).getAddonInfo('icon')
        else:
            thumbnail = get_icon_path('search')
        items.append({
            "label" : "[{}] {}".format(label,regex),
            #"path" : path,
            "path" : plugin.url_for('find_folder',regex=regex.encode("utf8"),path=path.encode("utf8"),label=label.encode("utf8"),depth='1'),
            "thumbnail" : thumbnail,
            'context_menu': context_items,
        })

    return items


@plugin.route('/favourite_folders')
def favourite_folders():
    favourites = plugin.get_storage('favourites')
    #renamers = plugin.get_storage('renamers')
    items = []
    for path,label in favourites.iteritems():
        #log((regex,path))
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=path, label=label.encode("utf8"), name="EVERYTHING"))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_folder, path=path, label=label.encode("utf8")))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Favourite', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_folder, path=path.encode("utf8")))))
        if plugin.get_setting('url.favourites') == 'true':
            display_label = "%s [COLOR dimgray][%s][/COLOR]" % (label,path)
        else:
            display_label = label
        if path.startswith('plugin://'):
            addon = re.search('plugin://(.*?)/',path+'/').group(1)
            thumbnail = xbmcaddon.Addon(addon).getAddonInfo('icon')
        else:
            thumbnail = get_icon_path('favourites')
        items.append({
            "label" : display_label,
            #"path" : path,
            "path" : plugin.url_for('folder',path=path.encode("utf8"),label=label.encode("utf8")),
            "thumbnail" : thumbnail,
            'context_menu': context_items,
        })

    return sorted(items, key=lambda k: k.get("label").lower())


@plugin.route('/service')
def service():
    #log("service")
    thread = threading.Thread(target=service_thread)
    thread.daemon = True
    thread.start()


@plugin.route('/service_thread')
def service_thread():
    xbmcgui.Dialog().notification("Addon Recorder","starting",sound=False)


    #log("service_thread")
    ffmpeg = ffmpeg_location()
    if not ffmpeg:
        return

    regexes = plugin.get_storage('regexes')

    for (regex,path),label in regexes.iteritems():
        #log((regex,path))
        service_folder(regex,path,label,depth=1)

    trakt_movies_service()
    trakt_shows_service()

    #log("finished")
    xbmcgui.Dialog().notification("Addon Recorder","finished",sound=False)


def service_folder(regex,path,label,depth=1):
    #log(("service_folder",regex,path,label,depth))
    renamers = plugin.get_storage('renamers')
    recordings = plugin.get_storage('recordings')
    media = "video"
    response = get_directory(media,path)
    files = response["files"]
    #dir_items = []
    #file_items = []
    for f in files:
        original_label = f['label']

        search_label = remove_formatting(original_label)
        url = f['file']
        thumbnail = f['thumbnail']

        if f['filetype'] == 'directory':
            file_label = search_label

            if depth < plugin.get_setting('depth',int):
                service_folder(regex,url,file_label,depth=depth+1)

        elif f['filetype'] == 'file':
            #log(("found",label))
            if not re.search(regex,search_label,flags=re.I):
                continue
            #log(("record",url))

            if (regex,path) in renamers:
                from_regex,to_regex = json.loads(renamers[(regex,path)])
                record_label = re.sub(from_regex,to_regex,original_label)
            else:
                record_label = "[%s] %s" % (label,original_label)

            if record_label not in recordings.values():
                #log(("record_thread",url,record_label))
                record_thread(url,record_label)


def trakt_movies_service():
    user = plugin.get_setting('trakt.user')
    if not user:
        return
    movie_folders = plugin.get_storage("trakt_movies")
    trakt_movies = trakt_movies_watchlist(user)
    #log(trakt_movies)
    if not trakt_movies:
        return
    for (title,year) in trakt_movies:
        regex = title
        label = "%s (%s)" % (title,year)
        for path in movie_folders:
            service_folder(regex,path,label,depth=1)


def trakt_shows_service():
    user = plugin.get_setting('trakt.user')
    if not user:
        return
    trakt_shows_folders = plugin.get_storage("trakt_shows")
    trakt_shows = trakt_shows_collection(user)
    #log(trakt_shows)
    if not trakt_shows:
        return
    for title in trakt_shows:
        regex = title
        label = title
        for path in trakt_shows_folders:
            service_folder(regex,path,label,depth=1)


def trakt_movies_watchlist(user):
    headers = {
      'Content-Type': 'application/json',
      'trakt-api-version': '2',
      'trakt-api-key': ADDON.getSetting('trakt.api.key')
    }
    url = 'https://api.trakt.tv/users/%s/watchlist/movies'  % user
    log(("trakt",url))
    content = requests.get(url, headers=headers).content
    if not content:
        return
    json_movies = json.loads(content)
    movies = []
    for movie in json_movies:
        details = movie["movie"]
        title = details["title"]
        year = details["year"]
        movies.append((title,year))
    return movies


def trakt_shows_collection(user):
    headers = {
      'Content-Type': 'application/json',
      'trakt-api-version': '2',
      'trakt-api-key': ADDON.getSetting('trakt.api.key')
    }
    url = 'http://api.trakt.tv/users/%s/collection/shows' % user
    log(("trakt",url))
    r = requests.get(url, headers=headers)
    content = r.content
    json_shows = json.loads(content)
    shows = []
    for show in json_shows:
        details = show["show"]
        title = details["title"]
        shows.append(title)
    return shows


def get_recordings():
    filename = 'special://profile/addon_data/plugin.video.addon.recorder/recording.json'
    f = xbmcvfs.File(filename,'rb')
    try:
        recordings = json.load(f)
    except:
        recordings = dict()
    return recordings

def set_recordings(recordings):
    filename = 'special://profile/addon_data/plugin.video.addon.recorder/recording.json'
    f = xbmcvfs.File(filename,'wb')
    json.dump(recordings,f,indent=2)

def add_recording(name,url):
    recordings = get_recordings()
    recordings[url] = name
    set_recordings(recordings)

def remove_recording(url):
    recordings = get_recordings()
    del recordings[url]
    set_recordings(recordings)

def is_recording(url):
    recordings = get_recordings()
    return url in recordings


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


    filename = re.sub(r"[^\w' \[\]-]+", "", label, flags=re.UNICODE)
    recording_path = plugin.get_setting("download") + filename + ' ' + datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S') +'.ts'
    log(("filename",recording_path))

    seconds = 60*60*plugin.get_setting('recording.hours',int)
    cmd = cmd + ["-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "300", "-y", "-t", str(seconds), "-c", "copy"]
    cmd = cmd + ['-f', 'mpegts','-']
    log(("start",cmd))

    recordings[url] = original_label
    recordings.sync()
    add_recording(original_label,url)
    xbmcgui.Dialog().notification("Addon Recorder starting",original_label,sound=False)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=windows())
    video = xbmcvfs.File(recording_path,'wb')
    cancelled = False
    while True:
        if not is_recording(url):
            cancelled = True
            break
        data = p.stdout.read(1000000)
        if not data:
            break
        video.write(data)
    video.close()
    remove_recording(url)
    p.wait()
    log(("done",cmd))
    f = xbmcvfs.File(recording_path)
    size = f.size()
    log(("size",size))
    f.close()
    if (size < 1000000) or cancelled:
        del recordings[url]
        recordings.sync()
        log(("too small",url))


    xbmcgui.Dialog().notification("Addon Recorder finished",original_label,sound=False)



@plugin.route('/links')
def links():
    return find_links()

@plugin.cached(TTL=plugin.get_setting('ttl',int))
def find_links():
    items = []
    regexes = plugin.get_storage('regexes')

    for (regex,path),label in regexes.iteritems():
        items += find_folder(regex,path,label,depth=1)
    return items

#@plugin.cached(TTL=plugin.get_setting('ttl',int))
@plugin.route('/find_folder/<regex>/<path>/<label>/<depth>')
def find_folder(regex,path,label,depth=1):
    depth = int(depth)
    #log(("find_folder",regex,path,label,depth))

    recordings = plugin.get_storage('recordings')
    #log((regex,path))
    media = "video"
    response = get_directory(media,path)
    files = response["files"]
    dir_items = []
    file_items = []
    items = []
    for f in files:
        original_label = f['label']
        #log(original_label)
        #log(f)
        search_label = remove_formatting(original_label)
        url = f['file']
        thumbnail = f['thumbnail']

        if f['filetype'] == 'directory':
            #log("here")
            file_label = search_label
            #log(("directory",depth,file_label))
            if depth < plugin.get_setting('depth',int):
                #log("find_folder")
                items += find_folder(regex,url,file_label,depth=depth+1)

        elif f['filetype'] == 'file':
            #log(("found",label))
            if not re.search(regex,search_label,flags=re.I):
                continue
            record_label = "[%s] %s" % (label,original_label)

            #log((record_label,recordings.values()))
            if record_label in recordings.values():
                recorded = True
            else:
                recorded = False

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



@plugin.cached(TTL=plugin.get_setting('ttl',int))
def get_directory(media,path):
    try:
        response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
        log(response)
        return response
    except Exception as e:
        log(e)
        return {"files":[]}



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
    recordings = plugin.get_storage('recordings')
    favourites = plugin.get_storage('favourites')
    trakt_movies = plugin.get_storage('trakt_movies')
    trakt_shows = plugin.get_storage('trakt_shows')
    label = label.decode("utf8")
    #log(path)
    folders = plugin.get_storage('folders')
    media = "video"
    response = get_directory(media,path)
    files = response["files"]
    dir_items = []
    file_items = []
    for f in files:
        file_label = remove_formatting(f['label'])
        url = f['file']
        thumbnail = f['thumbnail']
        if not thumbnail:
            thumbnail = get_icon_path('unknown')

        if f['filetype'] == 'directory':
            if media == "video":
                window = "10025"
            elif media in ["music","audio"]:
                window = "10502"
            else:
                window = "10001"
            context_items = []
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=url, label=file_label.encode("utf8"), name="EVERYTHING"))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record_folder, path=url, label=file_label.encode("utf8")))))
            if url in favourites:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Favourite', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_favourite_folder, path=url))))
            else:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Favourite', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_folder, path=url, label=file_label.encode("utf8")))))
            if url in trakt_movies:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Trakt Movies Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_trakt_movie_folder, path=url))))
            else:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Trakt Movies Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_trakt_movie_folder, path=url, label=file_label.encode("utf8")))))
            if url in trakt_shows:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove Trakt Shows Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_trakt_shows_folder, path=url))))
            else:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Trakt Shows Folder', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_trakt_shows_folder, path=url, label=file_label.encode("utf8")))))

            dir_label = "[B]%s[/B]" % file_label

            dir_items.append({
                'label': dir_label,
                'path': plugin.url_for('folder', path=url, label=file_label.encode("utf8")),
                'thumbnail': f['thumbnail'],
                'context_menu': context_items,
            })
        else:
            record_label = "[%s] %s" % (label,file_label)


            context_items = []
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Rule', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_rule, path=path, label=label.encode("utf8"), name=file_label.encode("utf8")))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Record', 'XBMC.RunPlugin(%s)' % (plugin.url_for(record, url=url, label=record_label.encode("utf8")))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Favourite', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_favourite_folder, path=url, label=record_label.encode("utf8")))))

            if record_label in recordings.values():
                record_label = "[COLOR yellow]%s[/COLOR]" % record_label
                display_label = "[COLOR yellow]%s[/COLOR]" % file_label
            else:
                display_label = "%s" % file_label

            file_items.append({
                'label': display_label,
                'path': url,
                'thumbnail': f['thumbnail'],
                'context_menu': context_items,
                'is_playable': True,
                'info_type': 'Video',
                'info':{"mediatype": "episode", "title": file_label}
            })

    return dir_items + file_items


@plugin.route('/cancel_recordings')
def cancel_recordings():
    recordings = get_recordings()

    recordings_labels = [(k,v) for k,v in sorted(recordings.iteritems(),key=lambda x: x[1])]
    labels = [x[1] for x in recordings_labels]

    indexes = xbmcgui.Dialog().multiselect("Cancel recordings",labels)
    if indexes:
        for index in indexes:
            url = recordings_labels[index][0]
            remove_recording(url)


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
    recordings.sync()

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


@plugin.route('/clear_trakt_shows')
def clear_trakt_shows():
    trakt_shows = plugin.get_storage('trakt_shows')

    trakt_shows_labels = [(k,v) for k,v in sorted(trakt_shows.iteritems(),key=lambda x: x[1])]
    labels = [x[1] for x in trakt_shows_labels]

    indexes = xbmcgui.Dialog().multiselect("Clear trakt series folders",labels)
    if indexes:
        for index in indexes:
            url = trakt_shows_labels[index][0]
            del trakt_shows[url]


@plugin.route('/clear_trakt_movies')
def clear_trakt_movies():
    trakt_movies = plugin.get_storage('trakt_movies')

    trakt_movies_labels = [(k,v) for k,v in sorted(trakt_movies.iteritems(),key=lambda x: x[1])]
    labels = [x[1] for x in trakt_movies_labels]

    indexes = xbmcgui.Dialog().multiselect("Clear trakt movies folders",labels)
    if indexes:
        for index in indexes:
            url = trakt_movies_labels[index][0]
            del trakt_movies[url]


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
        if file.startswith('plugin://'):
            addon = re.search('plugin://(.*?)/',file+'/').group(1)
            thumbnail = xbmcaddon.Addon(addon).getAddonInfo('icon')
        else:
            thumbnail = get_icon_path('movie')
        items.append(
        {
            'label': label,
            'path': file,#plugin.url_for('select', title=title,year=year),
            'thumbnail':thumbnail,
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
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear Trakt Movies Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_trakt_movies))))
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Clear Trakt Shows Folders', 'XBMC.RunPlugin(%s)' % (plugin.url_for(clear_trakt_shows))))

    items.append(
    {
        'label': "Favourite Folders",
        'path': plugin.url_for('favourite_folders'),
        'thumbnail':get_icon_path('favourites'),
        'context_menu': context_items,
    })

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
    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Cancel Recordings', 'XBMC.RunPlugin(%s)' % (plugin.url_for(cancel_recordings))))
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

    if xbmc.getCondVisibility('system.platform.android'):
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Delete ffmpeg', 'XBMC.RunPlugin(%s)' % (plugin.url_for(delete_ffmpeg))))

    return items


if __name__ == '__main__':
    plugin.run()

