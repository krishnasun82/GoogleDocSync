#!/usr/bin/python
#
# Copyright [2011] Sundar Srinivasan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Sundar Srinivasan (krishna.sun@gmail.com) Twitter: @krishnasun

__author__ = ('Sundar Srinivasan')

import sys
import os
import getopt
import time

import gdata
import gdata.data
from gdata.docs import client
from gdata.docs import service

def usage():
    print 'python gdocload.py -u user -p password'
    print 'Options:'
    print ' -u | --user: gmail id'
    print ' -p | --pass: password'
    print ' -m | --mode: mode of operation'
    print '\t 1->sync Google doc with local (only upload, default)'
    print '\t 2->sync local with Google Doc (only download)'
    print '\t 3->sync on both sides'

def extractDirname(dirhtml):
    from lxml import html
    tree = html.fromstring(dirhtml)
    dirnames = [span.text for span in tree.xpath("//span")]
    return dirnames[0]

def getPyTime(Gtime):
    getts = Gtime.split('.', 1)
    return time.strptime(getts[0], "%Y-%m-%dT%H:%M:%S")
    
class GDocClient:
    """ Client class for GoogleDoc """
    BASE_PATH = '/feed/default/private/full'
    SOURCE = 'GDocClient'
    abbrev = dict()

    def __init__(self, user, pswd):
        """ Constructor accepts gmail id & password """
        self._user = user
        self.gdocService = service.DocsService()
        self.gdocService.ClientLogin(user, pswd, source=GDocClient.SOURCE)
        self.gdocClient = client.DocsClient(source=GDocClient.SOURCE)
        self.gdocClient.ssl = True
        self.gdocClient.http_client.debug = False
        self.gdocClient.ClientLogin(user, pswd, source=GDocClient.SOURCE)
        
        GDocClient.abbrev['document'] = 'doc'
        GDocClient.abbrev['presentation'] = 'ppt'
        GDocClient.abbrev['spreadsheet'] = 'xls'
                
    def _printDocFeed(self, feed):
        if not feed.entry:
            print 'No documents in feed'
        else:
            for entry in feed.entry:
                resid = entry.resourceId.text
                aclquery = service.DocumentAclQuery(resid)
                aclfeed = self.gdocService.GetDocumentListAclFeed(
                    aclquery.ToUri())
               # if 'owner' in aclfeed.entry:
                oe = [x for x in aclfeed.entry if x.role.value == 'owner']
                if len(oe) > 0:
                    print entry.title.text + "\t" \
                            + entry.GetDocumentType() + "\t" \
                            + entry.lastViewed.text
                    
    def listDocs(self, parent=None):
        if not parent:            
            self._printDocFeed(self.gdocService.GetDocumentListFeed())
        else:
            pdir = parent.title.text
            dquery = service.DocumentQuery()
            dquery.AddNamedFolder(self._user, pdir)
            self._printDocFeed(self.gdocService.Query(dquery.ToUri()))                          

    def createFolder(self, name, parent=None):
        folderQuery = service.DocumentQuery(categories=['folder'],
                                            params={'showfolders': 'true'})
        if parent:
            folderQuery.AddNamedFolder(self._user, parent.title.text)
        folderFeed = self.gdocService.Query(folderQuery.ToUri())
        namedEntry = [x for x in folderFeed.entry if x.title.text == name]
        if not namedEntry or len(namedEntry) == 0:
            namedEntry.append(self.gdocService.CreateFolder(name, parent))
        return namedEntry[0]

    def getDoc(self, name, parent):
        pdir = parent.title.text
        dquery = service.DocumentQuery()
        dquery.AddNamedFolder(self._user, pdir)
        dquery['title'] = name
        dquery['title-exact'] = 'true'
        dfeed = self.gdocService.Query(dquery.ToUri())
        if len(dfeed.entry) > 0:
            return dfeed.entry[0]
        return None
        
    def createDoc(self, name, parent):
        pdir = parent.title.text
        dquery = service.DocumentQuery()
        dquery.AddNamedFolder(self._user, pdir)
        dquery['title'] = name
        dquery['title-exact'] = 'true'
        dfeed = self.gdocService.Query(dquery.ToUri())
        if len(dfeed.entry) == 0:
            entry = self.gdocClient.Create(gdata.docs.data.DOCUMENT_LABEL, name,
                                       folder_or_id=parent.resourceId.text)
        else:
            entry = dfeed.entry[0]
        return entry

    def uploadGDoc(self, name, path, folder):
        ms = gdata.MediaSource(file_path=path, content_type='text/plain')
        newEntry = self.gdocService.Upload(ms, name, folder_or_uri=folder)
        return newEntry

    def downloadGDoc(self, doc, path):
        self.gdocService.Export(doc, path)

    def _syncFile(self, gdir, osdir, mode, doctype):
        dquery = service.DocumentQuery()
        dquery.AddNamedFolder(self._user, gdir.title.text)
        gfeed = self.gdocService.Query(dquery.ToUri())
        gdocs = [x for x in gfeed.entry if x.GetDocumentType() == doctype]      
        osfiles = os.listdir(osdir)
        gnames = [x.title.text for x in gdocs]
        docfiles = [x.split('.',1)[0] for x in osfiles if x.endswith('.'+GDocClient.abbrev[doctype])]

        # Exclusive Google docs
        if mode != 1:
            gexdocs = [x for x in gdocs if x.title.text not in docfiles]
            for gd in gexdocs:
                fpath = osdir + '/' + gd.title.text + '.' + GDocClient.abbrev[doctype]
                self.gdocService.Export(gd, fpath)

        # Exclusive local docs
        elif mode != 2:
            oexdocs = [x for x in docfiles if x not in gnames]
            for od in oexdocs:
                fpath = osdir + '/' + od + '.' + GDocClient.abbrev[doctype]
                ms = gdata.MediaSource(file_path=fpath,
                                   content_type=service.SUPPORTED_FILETYPES[ \
                    GDocClient.abbrev[doctype].upper()])
                entry = self.gdocService.Upload(ms, od, folder_or_uri=gdir)

        # Commons docs
        cdocs = [x for x in gdocs if x.title.text in docfiles]
        for cd in cdocs:
            getts = cd.lastViewed.text.split('.', 1)
            gt = time.strptime(getts[0], "%Y-%m-%dT%H:%M:%S")
            fpath = osdir + '/' + cd.title.text + '.' + GDocClient.abbrev[doctype]
            ot = time.gmtime(os.path.getmtime(fpath))
            if gt > ot and mode != 1:
                os.unlink(fpath)
                self.gdocService.Export(cd, fpath)
            elif gt < ot and mode != 2:
                dname = cd.title.text
                ms = gdata.MediaSource(file_path=fpath, \
                                   content_type=service.SUPPORTED_FILETYPES[ \
                    GDocClient.abbrev[doctype].upper()])
                entry = self.gdocService.Put(
                    ms, cd.GetEditMediaLink().href)
                
    def syncDoc(self, gdir, osdir, mode=1):
        for k in GDocClient.abbrev.keys():
            self._syncFile(gdir, osdir, mode, str(k))
                
if __name__ == '__main__':
    if len(sys.argv) < 5:
        usage()
        sys.exit(1)
    try:
        opt, args = getopt.getopt(
            sys.argv[1:], "hu:p:m:", ["help","user", "pass", "mode"])
    except getopt.GetoptError, gerr:
        print str(gerr)
        usage()
        sys.exit(1)
    user = None
    pswd = None
    mode = 1
    for o, a in opt:
        if o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-u', '--user'):
            user = a
        elif o in ('-p', '--pass'):
            pswd = a
        elif o in ('-m', '--mode'):
            mode = int(a) if a in ['1', '2', '3'] else 1
            
    client = GDocClient(user, pswd)
    bkpFolder = client.createFolder('Sync-doc')
    syncdirname = raw_input('Enter the sync folder name: ')
    syncdir = client.createFolder(syncdirname, bkpFolder)
    metadoc = client.getDoc('meta-doc', syncdir)
    dirname = str()
    if not metadoc:
        dirname = raw_input('Enter directory to be synced: ')
        dirname = os.path.abspath(dirname)
        if not os.path.isdir(dirname):
            print 'The given link:', dirname, 'is not a directory'
            sys.exit(1)
        mdoc = open('meta-doc', 'w')
        mdoc.write(dirname)
        mdoc.flush()
        mdoc.close()
        metadoc = client.uploadGDoc('meta-doc', './meta-doc', syncdir)
        os.unlink('./meta-doc')
    else:
        filePath = os.path.abspath('.')+'/meta-doc'
        client.downloadGDoc(metadoc, filePath)
        mdoc = open('meta-doc', 'r')
        dirhtml = mdoc.readline()
        dirname = extractDirname(dirhtml)        
        mdoc.close()
        os.unlink('./meta-doc')

    if not mode:
        mode = 1
    client.syncDoc(syncdir, dirname, mode)
                                       

                                    

    
        
    
                               
                               
    
    
