"""This module contains an implementation of a sort-orders.
"""
import abc
from functools import total_ordering

from maflib.util import abstractclassmethod
from maflib.locatable import Locatable


class SortOrder(object):
    """Base class for all sort orders.  Sub-classes should implement name and
    sortKey."""

    __metaclass__ = abc.ABCMeta

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    @abstractclassmethod
    def name(cls):
        """Returns the order's name."""

    @abc.abstractmethod
    def sort_key(self):
        """Function to generate the sort key for sorting records into this
        ordering"""

    @classmethod
    def all(cls):
        """Returns the known sort order classes."""
        return [
            Unknown,
            Unsorted,
            BarcodesAndCoordinate,
            Coordinate
        ]

    @classmethod
    def find(cls, sort_order_name):
        """Returns the sort order class by name.  Throws an exception if
        none was found"""
        sort_order = next(iter([so for so in SortOrder.all()
                                if so.name() == sort_order_name]), None)
        if not sort_order:
            sort_orders = ", ".join([s.name() for s in SortOrder.all()])
            raise ValueError("Could not find sort order '%s', options: %s"
                             % (sort_order_name, sort_orders))
        return sort_order

    def __str__(self):
        return self.name()


@total_ordering
class SortOrderKey(object):
    """A container for the key used to sort MafRecords.  Sub-classes should
    implement the __cmp__ method."""

    __metaclass__ = abc.ABCMeta

    def __lt__(self, other):
        """Compare less than"""
        return self.__cmp__(other) < 0

    def __eq__(self, other):
        """Compare equal"""
        return self.__cmp__(other) == 0

    @abc.abstractmethod
    def __cmp__(self, other):
        """Compares two objects, returning -1 if this is less than the other, 0
        if they are equal, and 1 otherwise."""

    @classmethod
    def compare(cls, this, that):
        """Convenience method for comparing two objects of the same type that
        have a total ordering."""
        if this is None and that is None:
            return 0
        elif this is None:
            return 1
        elif that is None:
            return -1
        else:
            return (this > that) - (this < that)


class Unknown(SortOrder):
    """Defines a sort order """

    def __init__(self, *args, **kwargs):
        super(Unknown, self).__init__(*args, **kwargs)

    @classmethod
    def name(cls):
        """Returns the order's name."""
        return "Unknown"

    def sort_key(self):
        """Returns the sort key, which is not implemented as sorting is not 
        valid for the Unknown sort order."""
        raise NotImplementedError("Sorting not supported for Unknown order.")


class Unsorted(SortOrder):
    """Defines a sort order based on the chromosome, start position, and end 
    position, in that order."""

    def __init__(self, *args, **kwargs):
        super(Unsorted, self).__init__(*args, **kwargs)

    @classmethod
    def name(cls):
        """Returns the order's name."""
        return "Unsorted"

    def sort_key(self):
        """Returns the sort key, which is not implemented as sorting is not 
        valid for the Unsorted sort order."""
        raise NotImplementedError("Sorting not supported for Unsorted order.")


class _CoordinateKey(SortOrderKey, Locatable):
    """A little class that aids in comparing records based on chromosome, 
    start position, and end position"""

    def __init__(self, record, contigs):
        if not issubclass(record.__class__, Locatable):
            raise ValueError("Record of type '%s' is not a subclass of "
                             "'Locatable'" % record.__class__.__name__)
        chromosome = record.chromosome
        if contigs:
            try:
                chromosome = contigs.index(chromosome)
            except ValueError:
                raise ValueError(
                    "Could not find contig '%s' in list of contigs: %s"
                    % (chromosome, ", ".join(contigs))
                )
        Locatable.__init__(self, chromosome, record.start, record.end)

    def __cmp__(self, other):
        diff = self.compare(self.chromosome, other.chromosome)
        if diff == 0:
            diff = self.compare(self.start, other.start)
        if diff == 0:
            diff = self.compare(self.end, other.end)
        return diff

    def __str__(self):
        return "\t".join(
            str(s) for s in [self.chromosome, self.start, self.end])


class Coordinate(SortOrder):
    """Defines a sort order based on the chromosome, start position, and end 
    position, in that order."""

    def __init__(self, fasta_index=None, contigs=None, *args, **kwargs):
        """
        provide either fasta_index or contigs

        :param fasta_index: the path to the FASTA index for defining 
        ordering across chromosomes.
        :param contigs: list of contigs for ordering
        """
        self._contigs = None
        if fasta_index:
            handle = open(fasta_index, "r")
            self._contigs = \
                [line.rstrip("\r\n").split("\t")[0] for line in handle]
            handle.close()
        elif contigs:
            assert isinstance(contigs, list), \
                "contigs must be a list, but {0} found".format(type(contigs))
            self._contigs = contigs[:]
        super(Coordinate, self).__init__(*args, **kwargs)

    @classmethod
    def name(cls):
        """Returns the order's name."""
        return "Coordinate"

    def sort_key(self):
        """Function to generate the sort key for sorting records into this
        ordering"""
        def key(record):
            """Gets the key"""
            return _CoordinateKey(record=record, contigs=self._contigs)
        return key


class _BarcodesAndCoordinateKey(_CoordinateKey):
    """A little class that aids in comparing records based on tumor barcode,
    matched normal barcode, chromosome, start position, and end position"""
    def __init__(self, record, contigs):
        self.tumor_barcode = record.value("Tumor_Sample_Barcode")
        self.normal_barcode = record.value("Matched_Norm_Sample_Barcode")
        super(_BarcodesAndCoordinateKey, self).__init__(record, contigs)

    def __cmp__(self, other):
        diff = self.compare(self.tumor_barcode, other.tumor_barcode)
        if diff == 0:
            diff = self.compare(self.normal_barcode, other.normal_barcode)
        if diff == 0:
            diff = super(_BarcodesAndCoordinateKey, self).__cmp__(other)
        return diff

    def __str__(self):
        return "\t".join([self.tumor_barcode, self.normal_barcode,
                          super(_BarcodesAndCoordinateKey, self).__str__()])


class BarcodesAndCoordinate(Coordinate):
    """Defines a sort order based on the tumor barcode, matched normal
    barcode, chromosome, start position, and end position, in that order."""

    def __init__(self, *args, **kwargs):
        super(BarcodesAndCoordinate, self).__init__(*args, **kwargs)

    @classmethod
    def name(cls):
        """Returns the order's name."""
        return "BarcodesAndCoordinate"

    def sort_key(self):
        """Function to generate the sort key for sorting records into this
        ordering"""
        def key(record):
            """Gets the key"""
            return _BarcodesAndCoordinateKey(record=record,
                                             contigs=self._contigs)
        return key


class SortOrderChecker(object):
    """Checks that the records given are in sorted order"""

    def __init__(self, sort_order):
        self._last_rec = None
        try:
            self._sort_f = sort_order.sort_key()
        except NotImplementedError:
            self._sort_f = None
            pass

    def add(self, rec):
        """Check that the given record is in order relative to the previous
        record"""
        return self.__iadd__(rec)

    def __iadd__(self, rec):
        if self._last_rec and self._sort_f:
            rec_key = self._sort_f(rec)
            last_rec_key = self._sort_f(self._last_rec)
            if rec_key < last_rec_key:
                raise ValueError("Records out of order\n%s\n%s" %
                                 (str(self._last_rec), str(rec)))
        self._last_rec = rec
        return self

    def __del__(self):
        self._last_rec = None
        self._sort_f = None


class SortOrderEnforcingIterator(object):
    """An iterator that enforces a sort order."""

    def __init__(self, _iter, sort_order):
        self._checker = SortOrderChecker(sort_order=sort_order)
        self._iter = _iter

    def __iter__(self):
        return self

    def next(self):
        """Gets the next element."""
        return self.__next__()

    def __next__(self):
        rec = next(self._iter)
        self._checker.add(rec)
        return rec
