import tempfile

from maflib.column_types import StringColumn, FloatColumn
from maflib.reader import *
from maflib.schemes import *
from maflib.tests.testutils import *
from maflib.util import captured_output
from maflib.validation import MafFormatException
from maflib.writer import *


class TestMafWriter(TestCase):
    Scheme = GdcV1_0_0_ProtectedScheme()
    Version = Scheme.version()
    AnnotationSpec = Scheme.annotation_spec()

    __version_line = "%s%s %s" % (MafHeader.HeaderLineStartSymbol, MafHeader.VersionKey, Version)
    __annotation_line = "%s%s %s" % (MafHeader.HeaderLineStartSymbol, MafHeader.AnnotationSpecKey, AnnotationSpec)

    class TestScheme(MafScheme):
        @classmethod
        def version(cls):
            return "test-version"

        @classmethod
        def annotation_spec(cls):
            return "test-annotation"

        @classmethod
        def __column_dict__(cls):
            return OrderedDict([("str1", StringColumn),
                                ("float", FloatColumn),
                                ("str2", StringColumn)])

    def test_empty_file(self):
        fd, path = tempfile.mkstemp()

        # No logging to stderr/stdout
        with captured_output() as (stdout, stderr):
            writer = MafWriter(path=path, header=MafHeader(),
                               validation_stringency=ValidationStringency.Silent)
            writer.close()
            self.assertEqual(read_lines(path), [])
            self.assertEqual(str(writer.header()), "")
        stdout = stdout.getvalue().rstrip('\r\n').split("\n")
        stderr = stderr.getvalue().rstrip('\r\n').split("\n")
        self.assertListEqual(stdout, [''])
        self.assertListEqual(stderr, [''])

        # Logging to stderr/stdout
        with captured_output() as (stdout, stderr):
            writer = MafWriter(path=path, header=MafHeader(),
                               validation_stringency=ValidationStringency.Lenient)
            writer.close()
            self.assertEqual(read_lines(path), [])
            self.assertEqual(str(writer.header()), "")
        stdout = stdout.getvalue().rstrip('\r\n').split("\n")
        stderr = stderr.getvalue().rstrip('\r\n').split("\n")
        self.assertListEqual(stdout, [''])
        self.assertListEqualAndIn(
            ['HEADER_MISSING_VERSION',
             'HEADER_MISSING_ANNOTATION_SPEC'],
            stderr)

        #  Exceptions
        with captured_output():
            with self.assertRaises(MafFormatException) as context:
                writer = MafWriter(path=path, header=MafHeader(),
                                   validation_stringency=ValidationStringency.Strict)
            self.assertEqual(context.exception.tpe,
                             MafValidationErrorType.HEADER_MISSING_VERSION)

        os.remove(path)

    def test_gz_support(self):
        fd, path = tempfile.mkstemp(suffix=".gz")

        lines = [TestMafWriter.__version_line,
                 TestMafWriter.__annotation_line,
                 "#key1 value1",
                 "#key2 value2"
                 ]
        with captured_output() as (stdout, stderr):
            header = MafHeader.from_lines(lines=lines)
            writer = MafWriter(path, header)
            writer.close()
            self.assertListEqual(read_lines(path), lines)
            self.assertEqual(str(writer.header()), "\n".join(lines))
        stdout = stdout.getvalue().rstrip('\r\n').split("\n")
        stderr = stderr.getvalue().rstrip('\r\n').split("\n")
        self.assertListEqual(stdout, [''])
        self.assertListEqual(stderr, [''])
        os.remove(path)

    def test_close(self):
        fd, path = tempfile.mkstemp()

        lines = [TestMafWriter.__version_line,
                 TestMafWriter.__annotation_line,
                 "#key1 value1",
                 "#key2 value2"
                 ]
        header = MafHeader.from_lines(lines=lines)
        writer = MafWriter(path, header)
        writer._handle.write("LAST")  # Naughty
        writer.close()
        self.assertListEqual(read_lines(path), lines + ["LAST"])

        with self.assertRaises(ValueError):
            writer._handle.write("Oh no")

    def add_records(self):
        scheme = TestMafWriter.TestScheme()
        fd, path = tempfile.mkstemp()

        header_lines = MafHeader.scheme_header_lines(scheme) \
                       + ["#key1 value1", "#key2 value2"]
        header = MafHeader.from_lines(lines=header_lines)
        writer = MafWriter(path, header)
        values = ["string2", "3.14", "string1"]
        record_line = MafRecord.ColumnSeparator.join(values)
        record = MafRecord.from_line(line=record_line,
                                     scheme=scheme,
                                     line_number=1)
        writer += record
        writer.write(record)
        writer.close()

        self.assertListEqual(read_lines(path),
                             header_lines + [record_line, record_line])

    def test_record_validation_error(self):
        scheme = TestMafWriter.TestScheme()
        fd, path = tempfile.mkstemp()

        # Create the header
        header_lines = MafHeader.scheme_header_lines(scheme) \
                       + ["#key1 value1", "#key2 value2"]
        header = MafHeader.from_lines(lines=header_lines,
                                      validation_stringency=ValidationStringency.Silent)

        # Create the record
        values = ["string2", "error", "string1"]
        record_line = MafRecord.ColumnSeparator.join(values)
        record = MafRecord.from_line(line=record_line,
                                     scheme=scheme,
                                     line_number=1,
                                     validation_stringency=ValidationStringency.Silent)

        # Write the header, and the record twice
        with captured_output() as (stdout, stderr):
            writer = MafWriter(path, header,
                               validation_stringency=ValidationStringency.Lenient)
            writer += record
            writer.write(record)
            writer.close()
        stdout = stdout.getvalue().rstrip('\r\n').split("\n")
        stderr = stderr.getvalue().rstrip('\r\n').split("\n")
        self.assertListEqual(stdout, [''])

        # The errors that should be written stderr
        errors = [
            "HEADER_UNSUPPORTED_VERSION",
            "HEADER_UNSUPPORTED_ANNOTATION_SPEC",
            "RECORD_COLUMN_WITH_NO_VALUE",
            "RECORD_COLUMN_WITH_NO_VALUE"
        ]
        self.assertListEqualAndIn(errors, stderr)

        # The second column should be None
        err_record_line = record_line.replace("error", "None")
        self.assertListEqual(read_lines(path),
                             header_lines + [err_record_line, err_record_line])