
# act likelihood, ported 11/6/2016 Zack Li
# original fortran by E. Calabrese, J. Dunkley 2016


import numpy as np 
from scipy.io import FortranFile # need this to read the fortran data format
from scipy import linalg # need this for cholesky decomposition and inverse

class ACTPol_s2:
	"""
	Likelihood object, written to be easy to modify for use in other software
	like Monte Python and CosmoHammer. 
	
	__init__ loads in the likelihood data
	loglike computes the likelihood given some C_l
	test is a utility function for checking if things are working correctly.

	"""
	def __init__(self, 
		data_dir, # set absolute path to data directory. it's the only mandatory input.
		print_version = False, # whether we print out stuff when initializing
		use_tt = True,
		use_te = True,
		use_ee = True,
		tt_lmax = 6000,
		nbin = 132, # total bin,
		lmax_win = 9000,
		bmax = 53, 
		sigc = 0.01, # ACTPol temperature calibration 
		b0 = 4, #first bin in TT
		nbintt = 42, #500-4000
		nbinte = 45, #250-4000
		nbinee = 45  #250-4000
		):
		"""
		The only mandatory initialization option here is 
		"""


		# set up all the config variables
		self.data_dir=data_dir
		self.use_tt=use_tt
		self.use_te=use_te
		self.use_ee=use_ee
		self.tt_lmax=tt_lmax
		self.nbin=nbin
		self.lmax_win=lmax_win
		self.bmax=bmax
		self.sigc=sigc
		self.b0=b0
		self.nbintt=nbintt
		self.nbinte=nbinte
		self.nbinee=nbinee



		self.version='ACTPol_s2_cmbonly_like'
		if print_version:
			print("Initializing ACTPol likelihood, version", self.version)

		# set up the data file names
		like_file    = self.data_dir + '/cl_cmb_aps2.dat'
		cov_file     = self.data_dir + '/c_matrix_actpol.dat'
		bbltt_file   = self.data_dir + '/BblMean.dat'
		bblte_file   = self.data_dir + '/BblMean_Cross.dat'
		bblee_file   = self.data_dir + '/BblMean_Pol.dat'

		# like_file loading
		try:
		    self.bval, self.X_data, self.X_sig = np.genfromtxt(
	    		like_file, 
	    		max_rows=self.nbin,
	    		delimiter = None, 
	    		unpack=True)
		except IOError:
			print("Couldn't load file", like_file)
			sys.exit()

		# cov_file loading
		try:
			f = FortranFile(cov_file, 'r')
			self.covmat = f.read_reals(dtype=float).reshape((self.nbin,self.nbin))
			for i_index in range(self.nbin):
				for j_index in range(i_index,self.nbin):
					self.covmat[i_index,j_index] = self.covmat[j_index,i_index] 
			# important: arrays in Fortran are 1-indexed, 
			# but arrays in Python are 0-indexed. :(
		except IOError:
			print("Couldn't load file", cov_file)
			sys.exit()

		# bbltt_file loading
		try:
		    self.win_func_tt = np.genfromtxt(
	    		bbltt_file, 
	    		max_rows=self.bmax,
	    		delimiter = None)
		except IOError:
			print("Couldn't load file", like_file)
			sys.exit()

		# bblte_file loading
		try:
		    self.win_func_te = np.genfromtxt(
	    		bblte_file, 
	    		max_rows=self.bmax,
	    		delimiter = None)
		except IOError:
			print("Couldn't load file", like_file)
			sys.exit()

		# bblee_file loading
		try:
		    self.win_func_ee = np.genfromtxt(
	    		bblee_file, 
	    		max_rows=self.bmax,
	    		delimiter = None)
		except IOError:
			print("Couldn't load file", like_file)
			sys.exit()

		# add an initial column of zeroes, since input data starts at l=2 and we need l = 1
		self.win_func_tt = np.hstack((np.transpose([np.zeros(self.bmax)]), self.win_func_tt ))
		self.win_func_te = np.hstack((np.transpose([np.zeros(self.bmax)]), self.win_func_te ))
		self.win_func_ee = np.hstack((np.transpose([np.zeros(self.bmax)]), self.win_func_ee ))


		if print_version:
			print("Finished initializing.")



	def loglike(self, cell_tt, cell_te, cell_ee, yp):
		"""
		Pass in the cell_tt, cell_te, cell_ee, and yp values, get 2 * log L out.
	    """

    	# ----- coding notes -----
		# python is ZERO indexed, so l = 1 corresponds to an index i = 0
		# fortran indices start at ONE
		# 
		# general rule for indexing in fortran to python:
		# array(a:b, c:d) in Fortran --> array[a-1:b, c-1:d] in Python
		# all of our data starts with l = 2

		X_model = np.zeros(self.nbin)
		Y = np.zeros(self.nbin)

		l_list = np.array( range(2,self.tt_lmax+1))

		cltt = np.zeros(self.lmax_win)
		clte = np.zeros(self.lmax_win)
		clee = np.zeros(self.lmax_win)


		# convert to regular C_l, get rid of weighting 
		cltt[1:self.tt_lmax] = cell_tt / l_list / (l_list+1.0)*2.0 * np.pi
		clte[1:self.tt_lmax] = cell_te / l_list / (l_list+1.0)*2.0 * np.pi
		clee[1:self.tt_lmax] = cell_ee / l_list / (l_list+1.0)*2.0 * np.pi


		cl_tt = np.dot( self.win_func_tt[:self.bmax, 1:self.lmax_win], cltt[1:self.lmax_win] )
		cl_te = np.dot( self.win_func_te[:self.bmax, 1:self.lmax_win], clte[1:self.lmax_win] )
		cl_ee = np.dot( self.win_func_ee[:self.bmax, 1:self.lmax_win], clee[1:self.lmax_win] )

		X_model[0:self.nbintt] = cl_tt[ self.b0-1: self.b0 - 1 + self.nbintt]# TT
		X_model[self.nbintt:self.nbintt+self.nbinte+1] = cl_te[:self.nbinte+1] * yp
		X_model[self.nbintt+self.nbinte: self.nbintt + self.nbinte + self.nbinee] = \
			cl_ee[:self.nbinee]*yp**2.0 
		
		Y = self.X_data - X_model
		tmp = np.zeros((self.nbin,1))
		tmp[:self.nbin] = np.transpose( np.array([X_model[:self.nbin+1]]) )
		cov_tot = self.covmat + (self.sigc**2.0) * np.dot( tmp, np.transpose(tmp) )

		# choose which data is used
		if (self.use_tt) and (not self.use_te) and (not self.use_ee):
			bin_no = self.nbintt
			diff_vec = Y[:bin_no]
			fisher = cov_tot[:bin_no,:bin_no]
		elif (not self.use_tt) and (self.use_te) and (not self.use_ee):
			bin_no = self.nbinte
			diff_vec = Y[self.nbintt:self.nbintt+bin_no]
			fisher = cov_tot[self.nbintt:self.nbintt+bin_no, self.nbintt:self.nbintt+bin_no]
		elif (not self.use_tt) and (not self.use_te) and (self.use_ee):
			bin_no = self.nbinee 
			diff_vec = Y[self.nbintt + self.nbinte: self.nbintt + self.nbinte + bin_no]
			fisher = cov_tot[ self.nbintt + self.nbinte : self.nbintt + self.nbinte + bin_no, \
				self.nbintt + self.nbinte:self.nbintt + self.nbinte + bin_no]
		elif self.use_tt and self.use_te and self.use_ee:
			bin_no = self.nbin 
			diff_vec = Y
			fisher = cov_tot 
		else:
			print("You've chosen a mode which isn't implemented.")

		# now invert the fisher (covmat), cholesky factor and then invert
		fisher = linalg.cho_solve( linalg.cho_factor(fisher), b = np.identity(bin_no) )
		fisher = np.transpose(fisher)

		ptemp = np.dot(fisher, diff_vec)
		like = np.sum(ptemp * diff_vec) / 2.0

		return like



	def test(self):
		"""
		This function tests out the basic functionality of this likelihood code.
	    """
		filename = self.data_dir + "planck2015.dat"

		tt_lmax = 6000
		dum1, cell_tt, cell_te, cell_ee, dum2, dum3 = \
			np.genfromtxt(filename, delimiter=None, unpack=True, max_rows=tt_lmax-1)
		like = self.loglike(cell_tt, cell_te, cell_ee, 1.0)

		print("Expected: 147.747797921459")
		print("Found   : " + '{0:.12f}'.format(2*like))


