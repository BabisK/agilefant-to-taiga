#!/usr/local/bin/python2.7
# encoding: utf-8
'''
 -- shortdesc

 is a description

It defines classes_and_methods

@author:     user_name

@copyright:  2016 organization_name. All rights reserved.

@license:    license

@contact:    user_email
@deffield    updated: Updated
'''

import sys
import os

import mysql.connector

from taiga import TaigaAPI

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from pydoc import describe
from email.policy import default
from taiga.models.models import Milestones

__all__ = []
__version__ = 0.1
__date__ = '2016-02-22'
__updated__ = '2016-02-22'

DEBUG = 0
TESTRUN = 0
PROFILE = 0

def migrate_products(conn, taiga, product=None):
    cursor = conn.cursor()
    
    query = ('SELECT name, description '
             'FROM backlogs '
             'WHERE backlogtype="Product" ')
    
    if product:
        query += 'AND name=%s'
        cursor.execute(query, (product,))
    else:
        cursor.execute(query)
    
    projects = []
    for (name, description) in cursor:
        if description == '':
            projects.append(taiga.projects.create(name, 'Describe this project'))
        else:
            projects.append(taiga.projects.create(name, description))
            
    for project in projects:
        migrate_stories(conn, taiga, project)
        migrate_iterations(conn, taiga, project)
    
    return projects

def migrate_iterations(conn, taiga, project):
    cursor = conn.cursor()
    
    query = ('SELECT prod.name, proj.name, iter.name, iter.startDate, iter.endDate '
             'FROM backlogs prod '
             'JOIN backlogs proj '
             'ON prod.id = proj.parent_id '
             'JOIN backlogs iter '
             'ON proj.id = iter.parent_id '
             'WHERE prod.name=%s')
    
    cursor.execute(query, (project.name,))
            
    milestones = []
    for (prod_name, proj_name, iter_name, iter_startDate, iter_endDate) in cursor:
        milestones.append(project.add_milestone(iter_name, iter_startDate, iter_endDate))
    
    for milestone in milestones:
        migrate_stories(conn, taiga, project, milestone)

def migrate_stories(conn, taiga, project, milestone=None):
    cursor = conn.cursor()
    
    #points = project.list_points()
    
    if milestone != None:
        query = ('SELECT name, description, storyPoints '
                 'FROM stories '
                 'WHERE iteration_id IN '
                 '(SELECT iter.id '
                 'FROM backlogs prod '
                 'JOIN backlogs proj '
                 'ON prod.id = proj.parent_id '
                 'JOIN backlogs iter '
                 'ON proj.id = iter.parent_id '
                 'WHERE prod.name=%s AND iter.name=%s)')
    
        cursor.execute(query, (project.name, milestone.name))
    
        for (name, description, storyPoints) in cursor:
            project.add_user_story(name, description=description if description else '', milestone=milestone.id)
    else:
        query = ('SELECT name, description, storyPoints '
                 'FROM stories '
                 'WHERE iteration_id is null '
                 'AND (backlog_ID IN '
                 '(SELECT prod.id '
                 'FROM backlogs prod '
                 'JOIN backlogs proj '
                 'ON prod.id = proj.parent_id '
                 'WHERE prod.name=%s) '
                 'OR backlog_ID IN '
                 '(SELECT proj.id '
                 'FROM backlogs prod '
                 'JOIN backlogs proj '
                 'ON prod.id = proj.parent_id '
                 'WHERE prod.name=%s)) '
                 'AND id NOT IN '
                 '(SELECT parent_id '
                 'FROM stories '
                 'WHERE parent_id IS NOT null)')
        
        cursor.execute(query, (project.name, project.name))
        
        for (name, description, storyPoints) in cursor:
            #s = next((sp for sp in points if sp.name==str(storyPoints)), points[0])
            project.add_user_story(name, description=description if description else '')

class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

def main(argv=None):  # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by user_name on %s.
  Copyright 2016 organization_name. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument('-V', '--version', action='version', version=program_version_message)
        parser.add_argument('--agilefant-host', dest='agilefant_host', default='127.0.0.1', help='Host IP of the Agilefant database (default: 127.0.0.1')
        parser.add_argument('--agilefant-user', dest='agilefant_user', default='agilefant', help='Agilefant database user (default: agilefant)')
        parser.add_argument('--afilefant-password', dest='agilefant_password', default='agilefant', help='Agilefant database password for the defined user (default: agilefant)')
        parser.add_argument('--agilefant-db', dest='agilefant_db', default='agilefant', help='Agilefant database name (default: agilefant)')
        parser.add_argument('--taiga-host', dest='taiga_host', default='127.0.0.1', help='Host IP or FQDN of the Taiga API server (default: 127.0.0.1)')

        # Process arguments
        args = parser.parse_args()
        
        cnx = mysql.connector.connect(user=args.agilefant_user, password=args.agilefant_password, host=args.agilefant_host, database=args.agilefant_db)
        
        taiga = TaigaAPI(host='http://%s' % args.taiga_host)
        taiga.auth(username='admin',password='123123')
        
        migrate_products(cnx, taiga=taiga)
        
        cnx.close()
        
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except Exception as e:
        if DEBUG or TESTRUN:
            raise(e)
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2

if __name__ == "__main__":
    if DEBUG:
        sys.argv.append("-h")
    if TESTRUN:
        import doctest
        doctest.testmod()
    if PROFILE:
        import cProfile
        import pstats
        profile_filename = '_profile.txt'
        cProfile.run('main()', profile_filename)
        statsfile = open("profile_stats.txt", "wb")
        p = pstats.Stats(profile_filename, stream=statsfile)
        stats = p.strip_dirs().sort_stats('cumulative')
        stats.print_stats()
        statsfile.close()
        sys.exit(0)
    sys.exit(main())
