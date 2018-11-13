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



servicing = False

def Service():
    global servicing
    if servicing:
        return
    servicing = True
    xbmc.log("[plugin.video.addon.recorder] SERVICE",xbmc.LOGERROR)
    xbmc.executebuiltin('XBMC.RunPlugin(plugin://plugin.video.addon.recorder/service)')
    time.sleep(2)
    servicing = False

if plugin.get_setting('service',bool):
    monitor = xbmc.Monitor()
    xbmc.log("[plugin.video.addon.recorder] service started...",xbmc.LOGERROR)
    if plugin.get_setting('service.startup',bool):
        Service()
        plugin.set_setting('last.update', str(time.time()))
    while not monitor.abortRequested():
        if plugin.get_setting('service.type') == '1':
            interval = int(plugin.get_setting('service.interval'))
            waitTime = 3600 * interval
            ts = plugin.get_setting('last.update') or "0.0"
            lastTime = datetime.datetime.fromtimestamp(float(ts))
            now = datetime.datetime.now()
            nextTime = lastTime + datetime.timedelta(seconds=waitTime)
            td = nextTime - now
            timeLeft = td.seconds + (td.days * 24 * 3600)
            xbmc.log("[plugin.video.addon.recorder] Service waiting for interval %s" % waitTime,xbmc.LOGERROR)
        elif plugin.get_setting('service.type') == '2':
            next_time = plugin.get_setting('service.time')
            if next_time:
                hms = next_time.split(':')
                hour = hms[0]
                minute  = hms[1]
                now = datetime.datetime.now()
                next_time = now.replace(hour=int(hour),minute=int(minute),second=0,microsecond=0)
                if next_time < now:
                    next_time = next_time + datetime.timedelta(hours=24)
                td = next_time - now
                timeLeft = td.seconds + (td.days * 24 * 3600)
        if timeLeft <= 0:
            timeLeft = 1
        xbmc.log("[plugin.video.addon.recorder] Service waiting for %d seconds" % timeLeft,xbmc.LOGERROR)
        if timeLeft and monitor.waitForAbort(timeLeft):
            break
        xbmc.log("[plugin.video.addon.recorder] Service now triggered...",xbmc.LOGERROR)
        Service()
        now = time.time()
        plugin.set_setting('last.update', str(now))
else:
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        time.sleep(5)



del player_monitor
