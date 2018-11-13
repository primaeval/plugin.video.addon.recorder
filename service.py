# -*- coding: utf-8 -*-
import datetime, time
import xbmc
import xbmcaddon
import xbmcvfs
import sqlite3

from rpc import RPC
from xbmcswift2 import Plugin

plugin = Plugin()

def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')

def log(what):
    xbmc.log(repr(what),xbmc.LOGERROR)


class KodiPlayer(xbmc.Player):
    def __init__(self, *args, **kwargs):
        xbmc.Player.__init__(self)

    @classmethod
    def onPlayBackEnded(self):
        pass

    @classmethod
    def onPlayBackStopped(self):
        path = ""
        retry = 0
        while not path and retry < 50:
            path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
            retry=retry+1
            time.sleep(0.1)
        label = xbmc.getInfoLabel('ListItem.Label')

        conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/%s/replay.db' % addon_id()), detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        now = datetime.datetime.now() + datetime.timedelta(microseconds=1)  # add 1 microsecond, required for dbapi2
        if path:
            c.execute("INSERT OR REPLACE INTO links VALUES (?,?,?)", (label.decode("utf8"),path,now))
        conn.commit()
        conn.close()

    def onPlayBackStarted(self):
        try:
            file = self.getPlayingFile()
            log(file)
            response = RPC.player.get_item(playerid=1, properties=["title", "year", "thumbnail", "fanart", "showtitle", "season", "episode"])
            log(response)
        except:
            return
        item = response["item"]
        conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/%s/replay.db' % addon_id()), detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        now = datetime.datetime.now() + datetime.timedelta(microseconds=1)  # add 1 microsecond, required for dbapi2
        if file:
            c.execute("INSERT OR REPLACE INTO streams VALUES (?,?,?)", (item["label"],file,now))
        conn.commit()
        conn.close()



conn = sqlite3.connect(xbmc.translatePath('special://profile/addon_data/%s/replay.db' % addon_id()), detect_types=sqlite3.PARSE_DECLTYPES)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS streams (title TEXT, file TEXT, date TIMESTAMP, PRIMARY KEY(file))')
c.execute('CREATE TABLE IF NOT EXISTS links (title TEXT, file TEXT, date TIMESTAMP, PRIMARY KEY(file))')
conn.commit()
conn.close()

player_monitor = KodiPlayer()


def do_update():
    global last_update
    log("do_update")
    xbmc.executebuiltin('XBMC.RunPlugin(plugin://plugin.video.addon.recorder/service)')
    last_update = datetime.datetime.now()

last_update = datetime.datetime(1970,1,1)

if plugin.get_setting('service',bool) and plugin.get_setting('service.startup',bool):
    do_update()

monitor = xbmc.Monitor()
while not monitor.abortRequested():
    time_left = 10
    update = False
    if plugin.get_setting('service',bool):
        if plugin.get_setting('service.type',int) == 1:
            interval = plugin.get_setting('service.interval',int)
            next_update = last_update + interval*10 #3600
            log(("next_update",next_update))
            now = time.time()
            if now > next_update:
                time_left = 1
                update = True
            else:
                time_left = next_update - now
        elif plugin.get_setting('service.type',int) == 2:
            hms = plugin.get_setting('service.time',str).split(':')
            log(hms)
            hour = hms[0]
            minute  = hms[1]
            now = datetime.datetime.now()
            next_time = now.replace(hour=int(hour),minute=int(minute),second=0,microsecond=0)
            if next_time < now:
                next_time = next_time + datetime.timedelta(hours=24)
            last_time = next_time - datetime.timedelta(hours=24)
            td = next_time - now
            time_left = td.seconds + (td.days * 24 * 3600)
            elapsed = now - last_update
            since = now-last_time
            log(("last_time,next_time,since,until",last_time,next_time,now-last_time,next_time-now))
            log(("now,last_update,elapsed,time_left",now,last_update,elapsed,time_left))
            if elapsed > datetime.timedelta(hours=24):
                update = True
            if since > datetime.timedelta(hours=24):
                update = True 
            

    log(("time_left",time_left))
    if update:
        if plugin.get_setting('service',bool) and plugin.get_setting('service.type',int) != 0:
            log("update")
            do_update()
    log("tick")
    time.sleep(5)


del player_monitor
