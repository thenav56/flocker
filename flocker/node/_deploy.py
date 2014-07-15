# Copyright Hybrid Logic Ltd.  See LICENSE file for details.
# -*- test-case-name: flocker.node.test.test_deploy -*-

"""
Deploy applications on nodes.
"""

from .gear import GearClient, PortMap
from ._model import Application, StateChanges


class Deployer(object):
    """
    Start and stop containers.
    """
    def __init__(self, gear_client=None, volume_service):
        """
        :param IGearClient gear_client: The gear client API to use in
            deployment operations. Default ``GearClient``.
        :param VolumeService volume_service: The volume manager for this node.
        """
        if gear_client is None:
            gear_client = GearClient(hostname=b'127.0.0.1')
        self._gear_client = gear_client
        self._volume_service = VolumeService()

    def start_container(self, application):
        """
        Launch the supplied application as a `gear` unit.

        :param Application application: The ``Application`` to create and
            start.
        :returns: A ``Deferred`` which fires with ``None`` when the application
           has started.
        """
        if application.ports is not None:
            port_maps = map(lambda p: PortMap(internal_port=p.internal_port,
                                              external_port=p.external_port),
                            application.ports)
        else:
            port_maps = []
        return self._gear_client.add(application.name,
                                     application.image.full_name,
                                     ports=port_maps,
                                     )

    def stop_container(self, application):
        """
        Stop and disable the application.

        :param Application application: The ``Application`` to stop.
        :returns: A ``Deferred`` which fires with ``None`` when the application
            has stopped.
        """
        unit_name = application.name
        return self._gear_client.remove(unit_name)

    def discover_node_configuration(self):
        """
        List all the ``Application``\ s running on this node.

        :returns: A ``Deferred`` which fires with a list of ``Application``
            instances.
        """
        d = self._gear_client.list()

        def applications_from_units(units):
            volumes = self._volume_service.enumerate()
            volumes.addCallback(lambda volumes: set([
                volume.name for volume in volumes
                if volume.uuid == self._volume_service.uuid]))

            def got_volumes(available_volumes):
                applications = []
                for unit in units:
                    # XXX: The container_image will be available on the
                    # Unit when
                    # https://github.com/ClusterHQ/flocker/issues/207 is
                    # resolved.
                    if unit.name in available_volumes:
                        # XXX Mountpoint is not available, see
                        # https://github.com/ClusterHQ/flocker/issues/289
                        volume = AttachedVolume(mountpoint=None)
                    else:
                        volume = None
                    applications.append(Application(name=unit.name,
                                                    volume=volume))
                return applications
            volumes.addCallback(got_volumes)
            return volumes
        d.addCallback(applications_from_units)
        return d

    def calculate_necessary_state_changes(self, desired_state, hostname):
        """
        Work out which changes need to happen to the local state to match
        the given desired state.

        :param Deployment desired_state: The intended configuration of all
            nodes.
        :param bytes hostname: The hostname of the node that this is running
            on.

        :return: A ``Deferred`` which fires with a ``StateChanges`` instance
            specifying which containers must be started and which must be
            stopped.
        """
        desired_node_applications = []
        for node in desired_state.nodes:
            if node.hostname == hostname:
                desired_node_applications = node.applications

        # XXX: This includes stopped units. See
        # https://github.com/ClusterHQ/flocker/issues/208
        d = self.discover_node_configuration()

        def find_differences(current_node_applications):
            # Compare the applications being changed by name only.  Other
            # configuration changes aren't important at this point.
            current_state = {app.name for app in current_node_applications}
            desired_state = {app.name for app in desired_node_applications}

            start_names = desired_state.difference(current_state)
            stop_names = current_state.difference(desired_state)

            start_containers = {
                app for app in desired_node_applications
                if app.name in start_names
            }
            stop_containers = {
                app for app in current_node_applications
                if app.name in stop_names
            }

            return StateChanges(
                containers_to_start=start_containers,
                containers_to_stop=stop_containers,
            )
        d.addCallback(find_differences)
        return d
