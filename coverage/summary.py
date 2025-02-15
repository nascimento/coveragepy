# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/nedbat/coveragepy/blob/master/NOTICE.txt

"""Summary reporting"""

import sys

from coverage import env
from coverage.report import get_analysis_to_report
from coverage.results import Numbers
from coverage.misc import NotPython, CoverageException, output_encoding


class SummaryReporter(object):
    """A reporter for writing the summary report."""

    def __init__(self, coverage):
        self.coverage = coverage
        self.config = self.coverage.config
        self.branches = coverage.get_data().has_arcs()
        self.outfile = None
        self.fr_analysis = []
        self.skipped_count = 0
        self.total = Numbers()
        self.fmt_err = u"%s   %s: %s"

    def writeout(self, line):
        """Write a line to the output, adding a newline."""
        if env.PY2:
            line = line.encode(output_encoding())
        self.outfile.write(line.rstrip())
        self.outfile.write("\n")

    def report(self, morfs, outfile=None):
        """Writes a report summarizing coverage statistics per module.

        `outfile` is a file object to write the summary to. It must be opened
        for native strings (bytes on Python 2, Unicode on Python 3).

        """
        self.outfile = outfile or sys.stdout

        self.coverage.get_data().set_query_contexts(self.config.report_contexts)
        for fr, analysis in get_analysis_to_report(self.coverage, morfs):
            self.report_one_file(fr, analysis)

        # Prepare the formatting strings, header, and column sorting.
        max_name = max([len(fr.relative_filename()) for (fr, analysis) in self.fr_analysis] + [5])
        fmt_name = u"%%- %ds  " % max_name
        fmt_skip_covered = u"\n%s file%s skipped due to complete coverage."

        header = (fmt_name % "Name") + u" Stmts   Miss"
        fmt_coverage = fmt_name + u"%6d %6d"
        if self.branches:
            header += u" Branch BrPart"
            fmt_coverage += u" %6d %6d"
        width100 = Numbers.pc_str_width()
        header += u"%*s" % (width100+4, "Cover")
        fmt_coverage += u"%%%ds%%%%" % (width100+3,)
        if self.config.show_missing:
            header += u"   Missing"
            fmt_coverage += u"   %s"
        rule = u"-" * len(header)

        column_order = dict(name=0, stmts=1, miss=2, cover=-1)
        if self.branches:
            column_order.update(dict(branch=3, brpart=4))

        # Write the header
        self.writeout(header)
        self.writeout(rule)

        # `lines` is a list of pairs, (line text, line values).  The line text
        # is a string that will be printed, and line values is a tuple of
        # sortable values.
        lines = []

        for (fr, analysis) in self.fr_analysis:
            try:
                nums = analysis.numbers

                args = (fr.relative_filename(), nums.n_statements, nums.n_missing)
                if self.branches:
                    args += (nums.n_branches, nums.n_partial_branches)
                args += (nums.pc_covered_str,)
                if self.config.show_missing:
                    args += (analysis.missing_formatted(branches=True),)
                text = fmt_coverage % args
                # Add numeric percent coverage so that sorting makes sense.
                args += (nums.pc_covered,)
                lines.append((text, args))
            except Exception:
                report_it = not self.config.ignore_errors
                if report_it:
                    typ, msg = sys.exc_info()[:2]
                    # NotPython is only raised by PythonFileReporter, which has a
                    # should_be_python() method.
                    if typ is NotPython and not fr.should_be_python():
                        report_it = False
                if report_it:
                    self.writeout(self.fmt_err % (fr.relative_filename(), typ.__name__, msg))

        # Sort the lines and write them out.
        if getattr(self.config, 'sort', None):
            position = column_order.get(self.config.sort.lower())
            if position is None:
                raise CoverageException("Invalid sorting option: {!r}".format(self.config.sort))
            lines.sort(key=lambda l: (l[1][position], l[0]))

        for line in lines:
            self.writeout(line[0])

        # Write a TOTAL line if had 1 or more files.
        self.writeout(rule)
        args = ("TOTAL", self.total.n_statements, self.total.n_missing)
        if self.branches:
            args += (self.total.n_branches, self.total.n_partial_branches)
        args += (self.total.pc_covered_str,)
        if self.config.show_missing:
            args += ("",)
        self.writeout(fmt_coverage % args)

        # Write other final lines.
        if not self.total.n_files and not self.skipped_count:
            raise CoverageException("No data to report.")

        if self.config.skip_covered and self.skipped_count:
            self.writeout(
                fmt_skip_covered % (self.skipped_count, 's' if self.skipped_count > 1 else '')
                )

        return self.total.n_statements and self.total.pc_covered

    def report_one_file(self, fr, analysis):
        """Report on just one file, the callback from report()."""
        nums = analysis.numbers
        self.total += nums

        no_missing_lines = (nums.n_missing == 0)
        no_missing_branches = (nums.n_partial_branches == 0)
        if self.config.skip_covered and no_missing_lines and no_missing_branches:
            # Don't report on 100% files.
            self.skipped_count += 1
        else:
            self.fr_analysis.append((fr, analysis))
