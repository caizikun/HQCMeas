# -*- coding: utf-8 -*-
#==============================================================================
# module : base_tasks.py
# author : Matthieu Dartiailh
# license : MIT license
#==============================================================================
"""
"""
from atom.api\
    import (Atom, Str, Int, Instance, Bool, Value, observe, Unicode, List,
            ForwardTyped, Typed, ContainerList, set_default, Callable, Dict)

from configobj import Section, ConfigObj
from threading import Thread
from itertools import chain
from inspect import cleandoc
from copy import deepcopy
import os

from ..utils.atom_util import member_from_str, tagged_members
from .tools.task_database import TaskDatabase
from .tools.task_decorator import make_stoppable
from .tools.string_evaluation import safe_eval


PREFIX = '_a'


class BaseTask(Atom):
    """Base  class defining common members of all Tasks.

    This class basically defines the minimal skeleton of a Task in term of
    members and methods.

    """
    #--- Public API -----------------------------------------------------------
    task_class = Str().tag(pref=True)
    task_name = Str().tag(pref=True)
    task_label = Str()
    task_depth = Int()
    task_preferences = Instance(Section)
    task_database = Typed(TaskDatabase)
    task_database_entries = Dict(Str(), Value())
    task_path = Str()
    root_task = ForwardTyped(lambda: RootTask)
    process_ = Callable()

    def process(self):
        """ The main method of any task as it is this one which is called when
        the measurement is performed. This method should always be decorated
        with make_stoppable, and return True if things went well.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to be performed'
        raise NotImplementedError(cleandoc(err_str))

    def check(self, *args, **kwargs):
        """ Method used to check that everything is alright before starting a
        measurement.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to check that all parameters are ok'
        raise NotImplementedError(cleandoc(err_str))

    def register_in_database(self):
        """ Method used to create entries in the database.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to create its entry in the database'
        raise NotImplementedError(cleandoc(err_str))

    def unregister_from_database(self):
        """ Method used to delete entries from the database.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to delete its entry from the database'
        raise NotImplementedError(cleandoc(err_str))

    def register_preferences(self):
        """ Method used to create entries in the preferences object.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to create its entries in the preferences object'
        raise NotImplementedError(cleandoc(err_str))

    def update_preferences_from_members(self):
        """ Method used to update the entries in the preference object before
        saving.

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to update the entries in the preference object before saving'
        raise NotImplementedError(cleandoc(err_str))

    def update_members_from_preferences(self, **parameters):
        """ Method used to update the trait values using the info extracted
        from a config file.

        Parameters:
        ----------
        parameters : dict

        """
        err_str = 'This method should be implemented by subclasses of\
        AbstractTask. This method is called when the program requires the task\
        to update update the trait values using the info extracted from\
        a config file.'
        raise NotImplementedError(cleandoc(err_str))

    def accessible_database_entries(self):
        """ Convenience to get the accesible entries in the database.

        """
        return self.task_database.list_accessible_entries(self.task_path)

    def format_string(self, string):
        """ Replace values in {} by their corresponding database value.

        Parameters
        ----------
        string : str
            The string to format using the current values of the database.

        Returns
        -------
        formatted : str
            Formatted version of the input.

        """
        # If a cache evaluation of the string already exists use it.
        if string in self._format_cache:
            preformatted, ids = self._format_cache[string]
            vals = self.task_database.get_values_by_index(ids, PREFIX)
            return preformatted.format(**vals)

        # Otherwise if we are in running mode build a cache formatting.
        elif self.task_database.running:
            database = self.task_database
            aux_strings = string.split('{')
            if len(aux_strings) > 1:
                elements = [el
                            for aux in aux_strings
                            for el in aux.split('}')]
                database_indexes = database.get_entries_indexes(self.task_path,
                                                                elements[1::2])
                str_to_format = ''
                length = len(elements)
                for i in range(0, length, 2):
                    if i + 1 < length:
                        repl = PREFIX + str(database_indexes[elements[i + 1]])
                        str_to_format += elements[i] + '{' + repl + '}'
                    else:
                        str_to_format += elements[i]

                indexes = database_indexes.values()
                self._format_cache[string] = (str_to_format, indexes)
                vals = self.task_database.get_values_by_index(indexes, PREFIX)
                return str_to_format.format(**vals)
            else:
                self._format_cache[string] = (string, [])
                return string

        # In edition mode simply perfom the formatting as execution time is not
        # critical.
        else:
            database = self.task_database
            aux_strings = string.split('{')
            if len(aux_strings) > 1:
                elements = [el
                            for aux in aux_strings
                            for el in aux.split('}')]
                replacement_values = [database.get_value(self.task_path, key)
                                      for key in elements[1::2]]
                str_to_format = ''
                for key in elements[::2]:
                    str_to_format += key + '{}'

                str_to_format = str_to_format[:-2]

                return str_to_format.format(*replacement_values)
            else:
                return string

    def format_and_eval_string(self, string):
        """ Replace values in {} by their corresponding database value and eval

        Parameters
        ----------
        string : str
            The string to eval using the current values of the database.

        Returns
        -------
        formatted : str
            Formatted version of the input.

        """
        # If a cache evaluation of the string already exists use it.
        if string in self._eval_cache:
            preformatted, ids = self._eval_cache[string]
            vals = self.task_database.get_values_by_index(ids, PREFIX)
            return safe_eval(preformatted, vals)

        # Otherwise if we are in running mode build a cache evaluation.
        elif self.task_database.running:
            database = self.task_database
            aux_strings = string.split('{')
            if len(aux_strings) > 1:
                elements = [el
                            for aux in aux_strings
                            for el in aux.split('}')]
                database_indexes = database.get_entries_indexes(self.task_path,
                                                                elements[1::2])
                str_to_eval = ''
                length = len(elements)
                for i in range(0, length, 2):
                    if i + 1 < length:
                        repl = PREFIX + str(database_indexes[elements[i + 1]])
                        str_to_eval += elements[i] + repl
                    else:
                        str_to_eval += elements[i]

                indexes = database_indexes.values()
                self._eval_cache[string] = (str_to_eval, indexes)
                vals = self.task_database.get_values_by_index(indexes, PREFIX)
                return safe_eval(str_to_eval, vals)
            else:
                self._eval_cache[string] = (string, [])
                return safe_eval(string)

        # In edition mode simply perfom the evaluation as execution time is not
        # critical.
        else:
            database = self.task_database
            aux_strings = string.split('{')
            if len(aux_strings) > 1:
                elements = [el
                            for aux in aux_strings
                            for el in aux.split('}')]
                replacement_token = [PREFIX + str(i)
                                     for i in xrange(len(elements[1::2]))]
                repl = {PREFIX + str(i): database.get_value(self.task_path,
                                                            key)
                        for i, key in enumerate(elements[1::2])}
                str_to_format = ''
                for key in elements[::2]:
                    str_to_format += key + '{}'

                str_to_format = str_to_format[:-2]

                expr = str_to_format.format(*replacement_token)
                return safe_eval(expr, repl)
            else:
                return safe_eval(string)

    #--- Private API ----------------------------------------------------------

    #: Dictionary storing in infos necessary to perform fast formatting.
    #: Only used in running mode.
    _format_cache = Dict()

    #: Dictionary storing in infos necessary to perform fast evaluation.
    #: Only used in running mode.
    _eval_cache = Dict()

    def _default_task_class(self):
        """ Default value for the task_class member.

        """
        return self.__class__.__name__

    def _default_process_(self):
        """ Default value for the process_ member.

        """
        return self.process.__func__

    def _observe_task_name(self, change):
        """ Update the label any time the task name changes.

        """
        new = change['value']
        self.task_label = new + ' (' + self.task_class + ')'

    @observe('task_database_entries')
    def _update_database(self, change):
        """ Update the database content each time the database entries change.

        """
        if change['type'] == 'update':
            added = set(change['value']) - set(change['oldvalue'])
            removed = set(change['oldvalue']) - set(change['value'])
            if self.task_database:
                for entry in removed:
                    self.remove_from_database(self.task_name + '_' + entry)
                for entry in added:
                    new_value = deepcopy(self.task_database_entries[entry])
                    self.write_in_database(entry, new_value)


class SimpleTask(BaseTask):
    """ Task with no child task, written in pure Python.

    """
    #Class attribute specifying if instances of that class can be used in loop
    loopable = False

    #--- Public API -----------------------------------------------------------

    def write_in_database(self, name, value):
        """ Write a value to the right database entry.

        This method build a task specific database entry from the task_name
        and the name argument and set the database entry to the specified
        value.

        Parameters
        ----------
        name : str
            Simple name of the entry whose value should be set, ie no task name
            required.

        value:
            Value to give to the entry.

        """
        value_name = self.task_name + '_' + name
        return self.task_database.set_value(self.task_path, value_name, value)

    def get_from_database(self, full_name):
        """ Access to a database value using full name.

        Parameters
        ----------
        full_name : str
            Full name of the database entry, ie task_name + '_' + entry,
            where task_name is the name of the task that wrote the value in
            the database.

        """
        return self.task_database.get_value(self.task_path, full_name)

    def remove_from_database(self, full_name):
        """ Delete a database entry using its full name.

        Parameters
        ----------
        full_name : str
            Full name of the database entry, ie task_name + '_' + entry,
            where task_name is the name of the task that wrote the value in
            the database.

        """
        return self.task_database.delete_value(self.task_path, full_name)

    def register_in_database(self):
        """ Register the task entries into the database.

        """
        if self.task_database_entries:
            for entry in self.task_database_entries:
                # Perform a deepcopy of the entry value as I don't want to
                # alter that default value when delaing with the database later
                # on (apply for list and dict).
                value = deepcopy(self.task_database_entries[entry])
                self.task_database.set_value(self.task_path,
                                             self.task_name + '_' + entry,
                                             value)

    def unregister_from_database(self):
        """ Remove the task entries from the database.

        """
        if self.task_database_entries:
            for entry in self.task_database_entries:
                self.task_database.delete_value(self.task_path,
                                                self.task_name + '_' + entry)

    def register_preferences(self):
        """ Register the task preferences into the preferences system.

        """
        self.task_preferences.clear()
        for name in tagged_members(self, 'pref'):
            val = getattr(self, name)
            if isinstance(val, basestring):
                self.task_preferences[name] = val
            else:
                self.task_preferences[name] = repr(val)

    update_preferences_from_members = register_preferences

    def update_members_from_preferences(self, **parameters):
        """ Update the members values using a dict.

        Parameters
        ----------
        parameters : dict(str: str)
            Dictionary holding the new values to give to the members in string
            format.

        """
        for name, member in tagged_members(self, 'pref').iteritems():

            if name not in parameters:
                continue

            value = parameters[name]
            converted = member_from_str(member, value)
            setattr(self, name, converted)

    def make_parallel(self, pool, switch=''):
        """ Make the execution of a task happens in parallel.

        This method should be called in __init__ when there is no need to
        wait for the process method to return to start the next task,ie the
        process method decorated don't use any data succeptible to be corrupted
        by the next task.

        Parameters
        ----------
        pool : str
            Name of the pool this task is part of.

        switch : str
            Name of the member indicating whether or not to run this task in
            parallel.

        """
        par = self._parallel
        par['pool'] = pool
        par['activated'] = getattr(self, switch, True)
        if switch:
            self.observe('switch', self._redefine_process_)
        self._redefine_process_()

    def make_wait(self, wait=[], no_wait=[]):
        """ Make the execution of a task wait for the completion fo others.

        This method should be be called in __init__ when the process method
        need to access data in the database or need to be sure that physical
        quantities reached their expected values.

        Parameters
        ----------
        wait : list(str)
            Names of the pools this task waits to complete before starting .

        no_wait : list(str)
            Names of the pools this task does not wait to complete before
            starting .

        This parameters are mutually exclusive.
        """
        _wait = self._wait
        _wait['wait'] = wait
        _wait['no_wait'] = no_wait
        self._redefine_process_()

    #--- Private API ----------------------------------------------------------

    # Is the task parallel and what is its execution pool.
    _parallel = Dict(Str(), default={'activated': False, 'pool': ''})

    # Is the task waiting for execution pools and which.
    _wait = Dict(Str(), List())

    def _redefine_process_(self, change={}):
        """ Make process_ refects the parallel/wait settings.

        """
        if change:
            self._parallel['activated'] = change['value']
        process = self.process.__func__
        parallel = self._parallel
        if parallel['activated'] and parallel['pool']:
            process = self._make_parallel_process_(process, parallel['pool'])

        wait = self._wait
        if 'wait' in wait and 'no_wait' in wait:
            process = self._make_wait_process_(process,
                                               wait['wait'],
                                               wait['no_wait'])

        self.process_ = make_stoppable(process)

    @staticmethod
    def _make_parallel_process_(process, pool):
        """ Machinery to execute process_ in parallel.

        Create a wrapper around a method to execute it in a thread and
        register the thread.

        Parameters
        ----------
        process : method
            Method which should be wrapped to run in parallel.

        pool : str
            Name of the execution pool to which the created thread belongs.

        """
        def wrapper(*args, **kwargs):

            obj = args[0]
            thread = Thread(group=None,
                            target=process,
                            args=args,
                            kwargs=kwargs)
            all_threads = obj.task_database.get_value('root', 'threads')
            threads = all_threads.get(pool, None)
            if threads:
                threads.append(thread)
            else:
                all_threads[pool] = [thread]

            return thread.start()

        wrapper.__name__ = process.__name__
        wrapper.__doc__ = process.__doc__
        return wrapper

    @staticmethod
    def _make_wait_process_(process, wait, no_wait):
        """ Machinery to make process_ wait on other tasks execution.

        Create a wrapper around a method to wait for some threads to terminate
        before calling the method. Threads are grouped in execution pools.

        Parameters
        ----------
        process : method
            Method which should be wrapped to wait on threads.

        wait : list(str)
            Names of the execution pool which should be waited for.

        no_wait : list(str)
            Names of the execution pools which should not be waited for.

        Both parameters are mutually exlusive. If both lists are empty the
        execution will be differed till all the execution pools have completed
        their works.

        """
        if wait:
            def wrapper(*args, **kwargs):

                obj = args[0]
                all_threads = obj.task_database.get_value('root', 'threads')

                threads = chain.from_iterable([all_threads.get(w, [])
                                               for w in wait])
                for thread in threads:
                    thread.join()
                all_threads.update({w: [] for w in wait if w in all_threads})

                obj.task_database.set_value('root', 'threads', all_threads)
                return process(*args, **kwargs)

        elif no_wait:
            def wrapper(*args, **kwargs):

                obj = args[0]
                all_threads = obj.task_database.get_value('root', 'threads')

                pools = [k for k in all_threads if k not in no_wait]
                threads = chain.from_iterable([all_threads[p] for p in pools])
                for thread in threads:
                    thread.join()
                all_threads.update({p: [] for p in pools})

                obj.task_database.set_value('root', 'threads', all_threads)
                return process(*args, **kwargs)
        else:
            def wrapper(*args, **kwargs):

                obj = args[0]
                all_threads = obj.task_database.get_value('root', 'threads')

                threads = chain.from_iterable(all_threads.values())
                for thread in threads:
                    thread.join()
                all_threads.update({w: [] for w in all_threads})

                obj.task_database.set_value('root', 'threads', all_threads)
                return process(*args, **kwargs)

        wrapper.__name__ = process.__name__
        wrapper.__doc__ = process.__doc__

        return wrapper


class ComplexTask(BaseTask):
    """Task composed of several subtasks.

    """
    #--- Public API -----------------------------------------------------------

    #: List of all the children of the task.
    children_task = ContainerList(Instance(BaseTask)).tag(child=True)

    #: Flag indicating whether or not the task has a root task.
    has_root = Bool(False)

    def __init__(self, *args, **kwargs):
        super(ComplexTask, self).__init__(*args, **kwargs)
        self.observe('task_name', self._update_paths)
        self.observe('task_path', self._update_paths)
        self.observe('task_depth', self._update_paths)

    @make_stoppable
    def process(self):
        """ Run sequentially all child tasks.

        """
        result = True
        for child in self.children_task:
            result &= child.process_(child)

        return result

    def check(self, *args, **kwargs):
        """ Run test of all child tasks.

        """
        test = True
        traceback = {}
        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        check = aux.check(*args, **kwargs)
                        test = test and check[0]
                        traceback.update(check[1])
                else:
                    check = child.check(*args, **kwargs)
                    test = test and check[0]
                    traceback.update(check[1])

        return test, traceback

    def walk(self, members=[], callables={}):
        """ Explore the tasks hierarchy looking.

        Missing values will be filled with None.

        Parameters
        ----------
        members : list(str)
            Names of the members whose value should be retrieved.

        callables : dict(callable)
            Dict {name: callables} to call on every task in the hierarchy. Each
            callable should take as single argument the task.

        Returns
        -------
        answer : list
            List summarizing the result of the exploration.

        """
        answer = [self._answer(self, members, callables)]
        for task in self.children_task:
            if isinstance(task, SimpleTask):
                answer.append(self._answer(task, members, callables))
            else:
                answer.append(task.walk(members, callables))

        return answer

    def write_in_database(self, name, value):
        """ Write a value to the right database entry.

        This method build a task specific database entry from the task_name
        and the name argument and set the database entry to the specified
        value.

        Parameters
        ----------
        name : str
            Simple name of the entry whose value should be set, ie no task name
            required.

        value:
            Value to give to the entry.

        """
        value_name = self.task_name + '_' + name
        return self.task_database.set_value(self.task_path, value_name, value)

    def get_from_database(self, full_name):
        """ Access to a database value using full name.

        Parameters
        ----------
        full_name : str
            Full name of the database entry, ie task_name + '_' + entry,
            where task_name is the name of the task that wrote the value in
            the database.

        """
        return self.task_database.get_value(self.task_path, full_name)

    def remove_from_database(self, full_name):
        """ Delete a database entry using its full name.

        Parameters
        ----------
        full_name : str
            Full name of the database entry, ie task_name + '_' + entry,
            where task_name is the name of the task that wrote the value in
            the database.

        """
        return self.task_database.delete_value(self.task_path, full_name)

    def register_in_database(self):
        """ Create a node in the database and register all entries.

        This method registers both the task entries and all the tasks tagged
        as child.

        """
        if self.task_database_entries:
            for entry in self.task_database_entries:
                # Perform a deepcopy of the entry value as I don't want to
                # alter that default value when delaing with the database later
                # on (apply for list and dict).
                value = deepcopy(self.task_database_entries[entry])
                self.task_database.set_value(self.task_path,
                                             self.task_name + '_' + entry,
                                             value)

        self.task_database.create_node(self.task_path, self.task_name)

        #ComplexTask defines children_task so we always get something
        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        aux.register_in_database()
                else:
                    child.register_in_database()

    def unregister_from_database(self):
        """ Unregister all entries and delete associated database node.

        This method unregisters both the task entries and all the tasks tagged
        as child.

        """
        if self.task_database_entries:
            for entry in self.task_database_entries:
                self.task_database.delete_value(self.task_path,
                                                self.task_name + '_' + entry)

        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        aux.unregister_from_database()
                else:
                    child.unregister_from_database()

        self.task_database.delete_node(self.task_path, self.task_name)

    def register_preferences(self):
        """ Register the task preferences into the preferences system.

        This method registers both the task preferences and all the
        preferences of the tasks tagged as child.

        """
        self.task_preferences.clear()
        members = self.members()
        for name in members:
            # Register preferences.
            meta = members[name].metadata
            if meta and 'pref' in meta:
                val = getattr(self, name)
                if isinstance(val, basestring):
                    self.task_preferences[name] = val
                else:
                    self.task_preferences[name] = repr(val)

            # Find all tagged children.
            elif meta and 'child' in meta:
                child = getattr(self, name)
                if child:
                    if isinstance(child, list):
                        for i, aux in enumerate(child):
                            child_id = name + '_{}'.format(i)
                            self.task_preferences[child_id] = {}
                            aux.task_preferences = \
                                self.task_preferences[child_id]
                            aux.register_preferences()
                    else:
                        self.task_preferences[name] = {}
                        child.task_preferences = self.task_preferences[name]
                        child.register_preferences()

    def update_preferences_from_members(self):
        """ Update the values stored in the preference system.

        This method updates both the task preferences and all the
        preferences of the tasks tagged as child.

        """
        for name in tagged_members(self, 'pref'):
            val = getattr(self, name)
            if isinstance(val, basestring):
                self.task_preferences[name] = val
            else:
                self.task_preferences[name] = repr(val)

        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        aux.update_preferences_from_members()
                else:
                    child.update_preferences_from_members()

    def update_members_from_preferences(self, **parameters):
        """ Update the members values using a dict.

        Parameters
        ----------
        parameters : dict(str: str)
            Dictionary holding the new values to give to the members in string
            format.

        Notes
        -----
        This method is fairly powerful and can handle a lot of cases so
        don't override it without checking that it works.

        """
        for name, member in self.members().iteritems():

            # First we set the preference members
            meta = member.metadata
            if meta and 'pref' in meta:
                if name not in parameters:
                    continue

                # member_from_str handle containers
                value = parameters[name]
                validated = member_from_str(member, value)

                setattr(self, name, validated)

            # Then we deal with the choild tasks
            elif meta and 'child' in meta:
                if name not in parameters:
                    continue

                value = parameters[name]

                if isinstance(member, ContainerList):
                    validated = value
                else:
                    validated = value[0]

                setattr(self, name, validated)

    @observe('children_task')
    def on_children_modified(self, change):
        """Handle children being added or removed from the task.

        """
        # Do nothing in the absence of a root task.
        if self.has_root:
            # The whole list changed.
            if change['type'] == 'update':
                added = set(change['value']) - set(change['oldvalue'])
                removed = set(change['oldvalue']) - set(change['value'])
                for child in removed:
                    self._child_removed(child)
                for child in added:
                    self._child_added(child)

            # An operation has been performed on the list.
            elif change['type'] == 'container':
                op = change['operation']

                # Children have been added
                if op in ('__iadd__', 'append', 'extend', 'insert'):
                    if 'item' in change:
                        self._child_added(change['item'])
                    if 'items' in change:
                        for child in change['items']:
                            self._child_added(child)

                # Children have been removed.
                elif op in ('__delitem__', 'remove', 'pop'):
                    if 'item' in change:
                        self._child_removed(change['item'])
                    if 'items' in change:
                        for child in change['items']:
                            self._child_removed(child)

                # One child was replaced.
                elif op in ('__setitem__',):
                    old = change['olditem']
                    if isinstance(old, list):
                        for child in old:
                            self._child_removed(child)
                    else:
                        self._child_removed(old)

                    new = change['newitem']
                    if isinstance(new, list):
                        for child in new:
                            self._child_added(child)
                    else:
                        self._child_added(new)

    #--- Private API ----------------------------------------------------------

    #@observe('task_name, task_path, task_depth')
    def _update_paths(self, change):
        """Takes care that the paths, the database and the task names remains
        coherent.

        """
        if change['type'] == 'update':
            name = change['name']
            new = change['value']
            old = change.get('oldvalue', None)
            if self.has_root:
                if name == 'task_name':
                    self.task_database.rename_node(self.task_path, new, old)
                    for name in tagged_members(self, 'child'):
                        child = getattr(self, name)
                        if child:
                            if isinstance(child, list):
                                for aux in child:
                                    aux.task_path = self.task_path + '/' + new
                            else:
                                child.task_path = self.task_path + '/' + new
                elif name == 'task_path':
                    for name in tagged_members(self, 'child'):
                        child = getattr(self, name)
                        if child:
                            if isinstance(child, list):
                                for aux in child:
                                    aux.task_path = new + '/' + self.task_name
                            else:
                                child.task_path = new + '/' + self.task_name
                elif name == 'task_depth':
                    for name in tagged_members(self, 'child'):
                        child = getattr(self, name)
                        if child:
                            if isinstance(child, list):
                                for aux in child:
                                    aux.task_depth = new + 1
                            else:
                                child.task_depth = new + 1

    def _child_added(self, child):
        """Update the database, depth and preferences when a child is added.

        """
        child.task_depth = self.task_depth + 1
        child.task_database = self.task_database
        child.task_path = self.task_path + '/' + self.task_name

        #Give him its root so that it can proceed to any child
        #registration it needs to.
        child.root_task = self.root_task

        #Ask the child to register in database
        child.register_in_database()
        #Register anew preferences to keep the right ordering for the childs
        self.register_preferences()

    def _child_removed(self, child):
        """Update the database, depth and preferences when a child is removed.

        """
        self.register_preferences()
        child.unregister_from_database()

    def _observe_root_task(self, change):
        """ Observer.

        Make sure that all children get all the info they need to behave
        correctly when the task get its root parent (ie the task is now
        in a 'correct' environnement).

        """
        if change['value'] is None:
            return

        self.has_root = True
        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        aux.task_depth = self.task_depth + 1
                        aux.task_database = self.task_database
                        aux.task_path = self.task_path + '/' + self.task_name

                        # Give him its root so that it can proceed to any child
                        # registration it needs to.
                        aux.root_task = self.root_task
                else:
                    child.task_depth = self.task_depth + 1
                    child.task_database = self.task_database
                    child.task_path = self.task_path + '/' + self.task_name

                    # Give him its root so that it can proceed to any child
                    # registration it needs to.
                    child.root_task = self.root_task

    @staticmethod
    def _answer(obj, members, callables):
        """ Collect answers for the walk method.

        """
        answers = {m: getattr(obj, m, None) for m in members}
        answers.update({k: c(obj) for k, c in callables.iteritems()})
        return answers

from multiprocessing.synchronize import Event


class RootTask(ComplexTask):
    """Special task which is always the root of a measurement.

    """
    #--- Public API -----------------------------------------------------------

    #: Path to which log infos, prefernces, etc should be written by default.
    default_path = Unicode('').tag(pref=True)

    #: Header assembled just before the measure is run.
    default_header = Str('')

    #: Dict storing data needed at execution time (ex: drivers classes)
    run_time = Dict()

    #: Inter-process event signaling the task it should stop execution.
    should_stop = Instance(Event)

    # Seeting default values for the root task.
    has_root = set_default(True)
    task_name = set_default('Root')
    task_label = set_default('Root')
    task_depth = set_default(0)
    task_path = set_default('root')
    task_database_entries = set_default({'threads': {},
                                         'instrs': {},
                                         'default_path': ''})

    def __init__(self, *args, **kwargs):
        self.task_preferences = ConfigObj(indent_type='    ')
        self.task_database = TaskDatabase()
        super(RootTask, self).__init__(*args, **kwargs)
        self.register_in_database()
        self.root_task = self

    def check(self, *args, **kwargs):
        traceback = {}
        test = True
        if not os.path.isdir(self.default_path):
            test = False
            traceback[self.task_path + '/' + self.task_name] =\
                'The provided default path is not a valid directory'
        self.task_database.set_value('root', 'default_path', self.default_path)
        check = super(RootTask, self).check(*args, **kwargs)
        test = test and check[0]
        traceback.update(check[1])
        return test, traceback

    @make_stoppable
    def process(self):
        """ Run sequentially all child tasks, and close ressources.

        """
        result = True
        for child in self.children_task:
            result &= child.process_(child)
        pools = self.task_database.get_value('root', 'threads')
        for pool in pools.values():
            for thread in pool:
                thread.join()
        instrs = self.task_database.get_value('root', 'instrs')
        for instr_profile in instrs:
            instrs[instr_profile].close_connection()

        return result

    def register_in_database(self):
        """ Create a node in the database and register all entries.

        This method registers both the task entries and all the tasks tagged
        as child.

        """
        if self.task_database_entries:
            for entry in self.task_database_entries:
                # Perform a deepcopy of the entry value as I don't want to
                # alter that default value when delaing with the database later
                # on (apply for list and dict).
                # The 'instrs' and 'threads' entries were the principal .
                # motivations for using that mechanism.
                value = deepcopy(self.task_database_entries[entry])
                self.task_database.set_value(self.task_path,
                                             entry,
                                             value)

        self.task_database.create_node(self.task_path, self.task_name)

        #ComplexTask defines children_task so we always get something
        for name in tagged_members(self, 'child'):
            child = getattr(self, name)
            if child:
                if isinstance(child, list):
                    for aux in child:
                        aux.register_in_database()
                else:
                    child.register_in_database()

    #--- Private API ----------------------------------------------------------

    # Overrided here to give the child its root task right away.
    def _child_added(self, child):
        #Give the child all the info it needs to register
        child.task_depth = self.task_depth + 1
        child.task_database = self.task_database
        child.task_path = self.task_path

        #Give him its root so that it can proceed to any child
        #registration it needs to.
        child.root_task = self.root_task

        #Ask the child to register in database
        child.register_in_database()
        #Register anew preferences to keep the right ordering for the childs
        self.register_preferences()

    def _default_task_class(self):
        return ComplexTask.__name__

    @observe('default_path')
    def _update_default_path_in_database(self, change):
        """
        """
        new = change['value']
        if new:
            self.default_path = os.path.normpath(new)
            self.task_database.set_value('root', 'default_path',
                                         self.default_path)

    def _observe_task_name(self, change):
        """ Update the label any time the task name changes.

        """
        pass

KNOWN_PY_TASKS = [ComplexTask]

TASK_PACKAGES = ['tasks_util', 'tasks_logic']
