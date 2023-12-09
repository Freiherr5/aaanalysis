"""
Script for (backend class) Part object used to retrieve sequence parts for given sequences.
"""
import aaanalysis.utils as ut


# II Main Functions
class Parts:
    """
    Class for creating all sequence features necessary for CPP analysis:
    a) Target Middle Domain (TMD) or transmembrane domain for intramembrane proteases (IMP) substrates,
        whose length can vary between the protein sequences.
    b) Juxta Middle Domain (JMD) or juxtamembrane domain for IMP substrates,
        which flank the TMD N- and C-terminal with defined length.
    These sequence features can be derived from the total sequence, the TMD start and stop position,
        and the length of the JMD and the extended region (given for one side).

    Parameters
    ----------
    seq: sequence (e.g., amino acids sequence for protein)
    tmd_start: start position within the sequence of TMD
    tmd_stop: stop position within the sequence of the TMD
    jmd_n_len: length of JMD-N
    jmd_c_len: length of JMD-C
    """
    def __init__(self, seq=None, tmd_start=None, tmd_stop=None, jmd_n_len=10, jmd_c_len=10):
        self._seq = seq
        self._tmd_start = int(tmd_start)
        self._tmd_stop = int(tmd_stop)
        self._jmd_n_len = jmd_n_len
        self._jmd_c_len = jmd_c_len
        self._n_terminus_len = self._tmd_start - 1
        self._c_terminus_len = len(self._seq) - self._tmd_stop
        self.tmd = self._tmd()
        self.jmd_n = self._jmd_n()
        self.jmd_c = self._jmd_c()

    def _tmd(self):
        """Get sequence of TMD"""
        start = self._tmd_start - 1
        stop = self._tmd_stop
        return self._seq[start:stop]

    def _jmd_n(self):
        """Get sequence of N-terminal JMD"""
        if self._n_terminus_len >= self._jmd_n_len:
            start = self._tmd_start - (self._jmd_n_len + 1)
            stop = self._tmd_start - 1
            jmd_n = self._seq[start:stop]
        else:
            start = 0
            stop = self._tmd_start - 1
            part = self._seq[start:stop]
            jmd_n = ut.STR_AA_GAP * (self._jmd_n_len - len(part)) + part  # Add "-" (gap) for missing AA in JMD
        return jmd_n

    def _jmd_c(self):
        """Get sequence of C-terminal JMD"""
        if self._c_terminus_len >= self._jmd_c_len:
            start = self._tmd_stop
            stop = self._tmd_stop + self._jmd_c_len
            jmd_c = self._seq[start:stop]
        else:
            start = self._tmd_stop
            stop = self._tmd_stop + self._c_terminus_len
            part = self._seq[start:stop]
            jmd_c = part + ut.STR_AA_GAP * (self._jmd_c_len - len(part))  # Add "-" (gap) for missing AA in JMD
        return jmd_c


def create_parts(seq=None, tmd_start=None, tmd_stop=None, jmd_n_len=10, jmd_c_len=10):
    """Create JMD_N, TMD, and JMD_C using Parts object"""
    parts = Parts(seq=seq, tmd_start=tmd_start, tmd_stop=tmd_stop, jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len)
    jmd_n, tmd, jmd_c = parts.jmd_n, parts.tmd, parts.jmd_c
    return jmd_n, tmd, jmd_c