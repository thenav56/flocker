# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Test for real world behaviour of Cinder implementations, so we know when to
update our workarounds.
"""

from twisted.trial.unittest import SynchronousTestCase

from ..cinder import wait_for_volume
from ..test.blockdevicefactory import (
    ProviderType, get_blockdeviceapi_args,
)
from ....testtools import random_name


def cinder_volume_manager():
    cls, kwargs = get_blockdeviceapi_args(ProviderType.openstack)
    return kwargs["cinder_volume_manager"]


class VolumesCreateTests(SynchronousTestCase):
    """
    Tests for ``cinder.Client.volumes.create``.
    """
    def setUp(self):
        self.cinder_volumes = cinder_volume_manager()

    def test_create_metadata_is_listed(self):
        """
        ``metadata`` supplied when creating a volume is included when that
        volume is subsequently listed.
        """
        expected_metadata = {random_name(self): "bar"}

        new_volume = self.cinder_volumes.create(
            size=100,
            metadata=expected_metadata
        )
        self.addCleanup(self.cinder_volumes.delete, new_volume)
        listed_volume = wait_for_volume(
            volume_manager=self.cinder_volumes,
            expected_volume=new_volume,
        )

        expected_items = set(expected_metadata.items())
        actual_items = set(listed_volume.metadata.items())
        missing_items = expected_items - actual_items
        self.assertEqual(
            set(), missing_items,
            'Metadata {!r} does not contain the expected items {!r}'.format(
                actual_items, expected_items
            )
        )
    test_create_metadata_is_listed.todo = (
        'Rackspace API does not save the supplied metadata. '
        'See support ticket: 150422-ord-0000495'
    )


class VolumesSetMetadataTests(SynchronousTestCase):
    """
    Tests for ``cinder.Client.volumes.set_metadata``.
    """
    def setUp(self):
        self.cinder_volumes = cinder_volume_manager()

    def test_updated_metadata_is_listed(self):
        """
        ``metadata`` supplied to update_metadata is included when that
        volume is subsequently listed.
        """
        expected_metadata = {random_name(self): u"bar"}

        new_volume = self.cinder_volumes.create(size=100)
        self.addCleanup(self.cinder_volumes.delete, new_volume)

        listed_volume = wait_for_volume(
            volume_manager=self.cinder_volumes,
            expected_volume=new_volume,
        )

        self.cinder_volumes.set_metadata(new_volume, expected_metadata)

        listed_volume = wait_for_volume(
            volume_manager=self.cinder_volumes,
            expected_volume=new_volume
        )

        expected_items = set(expected_metadata.items())
        actual_items = set(listed_volume.metadata.items())
        missing_items = expected_items - actual_items

        self.assertEqual(set(), missing_items)
