# Third-party standards and external applications

The bridge implementation is original code under the accompanying MIT license.

`tests/fixtures/Codebook.xsd` is the REFI-QDA Codebook 1.0 schema, copyright
QDA software.org. It is an independent test oracle, not runtime code. Its exact
source, Git blob identity and SHA-256 are in `schema-provenance.json`.
The OpenQDA mirror identifies the REFI specification documents as MIT:
https://github.com/openqda/refi-tools/blob/main/docs/index.md
No implementation code from that mirror is included. Its software license is
separate from the standard document license.

MIT permission notice for the schema: permission is hereby granted, free of
charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to
the following conditions: the above copyright notice and this permission
notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Research applications, Python/Julia/Octave/R runtimes, DSH host code, commercial
licenses and user libraries are not bundled. Their own licenses apply. The host
test extracts installed DSH modules into a local test cache only.
