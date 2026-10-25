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

## Companion integrations added in 0.4.0

The optional MATLAB bundle is `lovedheart/dsh-matlab-mcp-plugin` 1.0.0 at
`d732d36ea281c9dfd59e3039c27559653c28e9ff`, Apache-2.0. Its own LICENSE is
retained in the separately distributed companion tarball. The MathWorks MATLAB
MCP server v0.15.0 is obtained separately from its official repository.

The optional Zotero package derives from `Hongcheng-LI/dsh-zotero` 0.2.2 at
`e4042d5139aa81d810b95928d63632f80a32a7ac`, MIT, copyright lhc.
The local `0.2.2-research.1` compatibility patch removes undefined optional
object fields at the native tool result boundary and rejects non-JSON values.
Original request logic and policy routing are preserved. Both compiled and
TypeScript source are patched. The original MIT license is retained in that
tarball and in `docs/compatibility/ZOTERO-LICENSE.md`; the source change is
documented in `docs/compatibility/zotero-lossless-json.patch.md`.
