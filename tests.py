__author__ = 'gabriel'
from network.itn import read_gml, ITNStreetNet
from network.streetnet import NetPath
from data import models
import os
import unittest
import settings
import numpy as np
from matplotlib import pyplot as plt
from point_process import utils

class TestNetworkData(unittest.TestCase):

    def setUp(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        IN_FILE = os.path.join(this_dir, 'test_data', 'mastermap-itn_417209_0_brixton_sample.gml')

        self.test_data = read_gml(IN_FILE)

        self.itn_net = ITNStreetNet()
        self.itn_net.load_from_data(self.test_data)

    def test_grid_index(self):
        xmin, xmax, ymin, ymax =  530850, 531900, 174550, 175500
        grid_edge_index = self.itn_net.build_grid_edge_index(xmin, xmax, ymin, ymax, 50)
        x_grid_expct = np.arange(xmin, xmax, 50)
        self.assertTrue(np.all(grid_edge_index.x_grid == x_grid_expct))

    def test_extent(self):
        expected_extent = (530960.0, 174740.0, 531856.023, 175436.0)
        for eo, ee in zip(expected_extent, self.itn_net.extent):
            self.assertAlmostEqual(eo, ee)

    def test_net_point(self):
        #Four test points - 1 and 3 on same segment, 2 on neighbouring segment, 4 long way away.
        #5 and 6 are created so that there are 2 paths of almost-equal length between them - they
        #lie on opposite sides of a 'square'
        x_pts = (
            531190,
            531149,
            531210,
            531198,
            531090
        )
        y_pts = (
            175214,
            175185,
            175214,
            174962,
            175180
        )
        xmin, ymin, xmax, ymax = self.itn_net.extent
        grid_edge_index = self.itn_net.build_grid_edge_index(xmin, xmax, ymin, ymax, 50)
        net_points = []
        snap_dists = []
        for x, y in zip(x_pts, y_pts):
            tmp = self.itn_net.closest_edges_euclidean(x, y, grid_edge_index=grid_edge_index)[0]
            net_points.append(tmp[0])
            snap_dists.append(tmp[0])

        # test net point subtraction
        self.assertIsInstance(net_points[1] - net_points[0], NetPath)
        self.assertAlmostEqual((net_points[1] - net_points[0]).length, (net_points[0] - net_points[1]).length)
        for i in range(len(net_points)):
            self.assertEqual((net_points[i] - net_points[i]).length, 0.)

        net_point_array = models.NetworkData(net_points)
        net_point_array_directed = models.DirectedNetworkData(net_points)

        self.assertFalse(np.any(net_point_array.distance(net_point_array).data.sum()))


if __name__ == "__main__":
    this_dir = os.path.join(settings.DATA_DIR, 'network_data')
    # IN_FILE = os.path.join(this_dir, 'mastermap-itn_544003_0_camden_buff2000.gml')
    IN_FILE = os.path.join(this_dir, 'mastermap-itn_417209_0_brixton_sample.gml')

    # test data is in a directory in the same path as this module called 'test_data'
    # this_dir = os.path.dirname(os.path.realpath(__file__))
    # IN_FILE = os.path.join(this_dir, 'test_data', 'mastermap-itn_417209_0_brixton_sample.gml')

    # usual loading procedure

    test_data = read_gml(IN_FILE)
    itn_net = ITNStreetNet()
    itn_net.load_from_data(test_data)

    # get the spatial extent of the network

    xmin, ymin, xmax, ymax = itn_net.extent

    # lay down some random points within that box
    num_pts = 50

    x_pts = np.random.rand(num_pts) * (xmax - xmin) + xmin
    y_pts = np.random.rand(num_pts) * (ymax - ymin) + ymin

    # now we want to snap them all to the network...
    # method A: do it in two steps...

    # A1: push them into a single data array for easier operation
    xy = models.DataArray.from_args(x_pts, y_pts)
    # A2: use the class method from_cartesian,
    net_point_array_a = models.NetworkData.from_cartesian(itn_net, xy, grid_size=50)  # grid_size defaults to 50

    # method B: do it manually, just to check
    # also going to take this opportunity to test a minor problem with closest_edges_euclidean

    grid_edge_index = itn_net.build_grid_edge_index(50)
    net_points = []
    snap_dists = []
    fail_idx = []
    for i, (x, y) in enumerate(zip(x_pts, y_pts)):
        tmp = itn_net.closest_edges_euclidean(x, y, grid_edge_index=grid_edge_index)
        if not len(tmp):
            # some of those calls fail when the grid_size is too small (e.g. 50 is actually too small)
            # the fall back should probably be a method that does not depend on the grid, which is what
            # closest_segments_euclidean_brute_force is designed to do
            # this method is MUCH slower but always finds an edge
            tmp = itn_net.closest_segments_euclidean_brute_force(x, y)
            fail_idx.append(i)
        else:
            tmp = tmp[0]
        net_points.append(tmp[0])
        snap_dists.append(tmp[1])

    net_point_array_b = models.NetworkData(net_points)

    # check these are the same

    print net_point_array_a == net_point_array_b  # this is just doing a point-by-point equality check behind the scenes

    # find the cartesian_coords after snapping
    xy_post_snap = net_point_array_a.to_cartesian()

    # plot showing the snapping operation

    # this separates the data arrays back into their constituent dims
    x_pre, y_pre = xy.separate
    x_post, y_post = xy_post_snap.separate

    fig = plt.figure()
    ax = fig.add_subplot(111)
    itn_net.plot_network(ax=ax, edge_width=7, edge_inner_col='w')
    ax.plot(x_pre, y_pre, 'ro')
    ax.plot(x_post, y_post, 'bo')
    [ax.plot([x_pre[i], x_post[i]], [y_pre[i], y_post[i]], 'k-') for i in range(xy.ndata)]

    # highlight failed points (where closest_edges_euclidean didn't find any snapped point) in black circles
    [ax.plot(x_pre[i], y_pre[i], marker='o', markersize=20, c='k', fillstyle='none') for i in fail_idx]

    # glue the network point array together with a time dimension - just take time at uniform intervals on [0, 1]
    st_net_point_array = models.NetworkSpaceTimeData(
        zip(np.linspace(0, 1, num_pts), net_points)
    )

    # compute linkages at a max delta t and delta d
    # i, j = utils.linkages(st_net_point_array, max_t=1.0, max_d=300.)