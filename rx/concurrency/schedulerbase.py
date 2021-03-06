from datetime import datetime, timedelta

from rx.core import Scheduler, Disposable
from rx.disposables import CompositeDisposable
from rx.internal.basic import default_now


class SchedulerBase(Scheduler):
    """Provides a set of static properties to access commonly used
    schedulers.
    """

    def invoke_action(self, action, state=None):
        ret = action(self, state)
        if isinstance(ret, Disposable):
            return ret

        return Disposable.empty()

    @staticmethod
    def invoke_rec_immediate(scheduler, pair):
        state = pair.get('state')
        action = pair.get('action')
        group = CompositeDisposable()

        def inner_action(state2=None):
            is_added = False
            is_done = [False]

            def schedule_work(_, state3):
                action(inner_action, state3)
                if is_added:
                    group.remove(d)
                else:
                    is_done[0] = True

                return Disposable.empty()

            d = scheduler.schedule(schedule_work, state2)
            if not is_done[0]:
                group.add(d)
                is_added = True

        action(inner_action, state)
        return group

    @staticmethod
    def invoke_rec_date(scheduler, pair, method):
        state = pair.get('first')
        action = pair.get('second')
        group = CompositeDisposable()

        def inner_action(state2, duetime):
            is_added = False
            is_done = [False]

            def schedule_work(_, state3):
                action(state3, inner_action)
                if is_added:
                    group.remove(d)
                else:
                    is_done[0] = True

                return Disposable.empty()

            d = getattr(scheduler, method)(duetime=duetime, action=schedule_work, state=state2)
            if not is_done[0]:
                group.add(d)
                is_added = True

        action(state, inner_action)
        return group

    def schedule_recursive(self, action, state=None):
        """Schedules an action to be executed recursively.

        Keyword arguments:
        :param types.FunctionType action: Action to execute recursively.
            The parameter passed to the action is used to trigger recursive
            scheduling of the action.
        :param T state: State to be given to the action function.

        :returns: The disposable object used to cancel the scheduled action
            (best effort).
        :rtype: Disposable
        """

        def scheduled_action(scheduler, pair):
            return self.invoke_rec_immediate(scheduler, pair)

        return self.schedule(scheduled_action, dict(state=state, action=action))

    def schedule_recursive_with_relative(self, duetime, action):
        """Schedules an action to be executed recursively after a specified
        relative due time.

        Keyword arguments:
        action -- {Function} Action to execute recursively. The parameter passed
            to the action is used to trigger recursive scheduling of the action
            at the specified relative time.
         duetime - {Number} Relative time after which to execute the action for
            the first time.

        Returns the disposable {Disposable} object used to cancel the scheduled
        action (best effort)."""

        def action1(_action, this=None):
            def func(dt):
                this(_action, dt)
            _action(func)
        return self.schedule_recursive_with_relative_and_state(duetime, action1, state=action)

    def schedule_recursive_with_relative_and_state(self, duetime, action, state):
        """Schedules an action to be executed recursively after a specified
        relative due time.

        Keyword arguments:
        :param T state: State passed to the action to be executed.
        :param types.FunctionType action: Action to execute recursively. The
            last parameter passed to the action is used to trigger recursive
            scheduling of the action, passing in the recursive due time and
            invocation state.
        :param int|timedelta duetime: Relative time after which to execute the
            action for the first time.

        :returns: The disposable object used to cancel the scheduled action
            (best effort).
        :rtype: Disposable
        """

        def action1(s, p):
            return self.invoke_rec_date(s, p, 'schedule_relative')

        return self.schedule_relative(duetime, action1,
                                      state={"first": state, "second": action})

    def schedule_recursive_with_absolute(self, duetime, action):
        """Schedules an action to be executed recursively at a specified
        absolute due time.

        Keyword arguments:
        action -- {Function} Action to execute recursively. The parameter
            passed to the action is used to trigger recursive scheduling of
            the action at the specified absolute time.
        duetime {Number} Absolute time at which to execute the action for
            the first time.

        Returns the disposable {Disposable} object used to cancel the
        scheduled action (best effort)."""

        def action1(_action, this=None):
            def func(dt):
                this(_action, dt)
            _action(func)
        return self.schedule_recursive_with_absolute_and_state(duetime=duetime,
                                                               action=action1,
                                                               state=action)

    def schedule_recursive_with_absolute_and_state(self, duetime, action, state):
        """Schedules an action to be executed recursively at a specified
        absolute due time.

        Keyword arguments:
        state -- {Mixed} State passed to the action to be executed.
        action -- {Function} Action to execute recursively. The last parameter
            passed to the action is used to trigger recursive scheduling of the
            action, passing in the recursive due time and invocation state.
        duetime -- {Number} Absolute time at which to execute the action for the
            first time.
        Returns the disposable {Disposable} object used to cancel the scheduled
        action (best effort)."""

        def action2(scheduler, pair):
            return self.invoke_rec_date(scheduler, pair, method='schedule_absolute')

        return self.schedule_absolute(
            duetime=duetime, action=action2,
            state={"first": state, "second": action})

    @property
    def now(self):
        """Represents a notion of time for this scheduler. Tasks being
        scheduled on a scheduler will adhere to the time denoted by this
        property.
        """

        return default_now()

    @classmethod
    def to_relative(cls, timespan):
        """Converts time value to milliseconds"""

        if isinstance(timespan, datetime):
            timespan = timespan - datetime.fromtimestamp(0)
            timespan = int(timespan.total_seconds()*1000)
        elif isinstance(timespan, timedelta):
            timespan = int(timespan.total_seconds()*1000)

        return int(timespan)

    @classmethod
    def to_datetime(cls, duetime):
        """Converts time value to datetime"""

        if isinstance(duetime, timedelta):
            duetime = datetime.fromtimestamp(0) + duetime
        elif not isinstance(duetime, datetime):
            duetime = datetime.fromtimestamp(duetime/1000.0)

        return duetime

    @classmethod
    def to_timedelta(cls, timespan):
        """Converts time value to timedelta"""

        if isinstance(timespan, datetime):
            timespan = timespan - datetime.fromtimestamp(0)
        elif not isinstance(timespan, timedelta):
            timespan = timedelta(milliseconds=timespan)

        return timespan

    @classmethod
    def normalize(cls, timespan):
        """Normalizes the specified timespan value to a positive value.

        Keyword arguments:
        :param int|timedelta timespan: The time span value to normalize.

        :returns: The specified Timespan value if it is zero or positive;
            otherwise, 0
        :rtype: int|timedelta
        """

        nospan = 0 if isinstance(timespan, int) else timedelta(0)
        if not timespan or timespan < nospan:
            timespan = nospan

        return timespan
