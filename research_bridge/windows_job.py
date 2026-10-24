"""Own a Windows process tree, including launchers which outlive their parent.

Create the child suspended, attach it to a kill-on-close Job Object, then resume
its initial thread. No process is selected by executable name or user session.
"""
import ctypes
from ctypes import wintypes

class IO_COUNTERS(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ("ReadOperationCount","WriteOperationCount","OtherOperationCount","ReadTransferCount","WriteTransferCount","OtherTransferCount")]

class BASIC_LIMITS(ctypes.Structure):
    _fields_=[("PerProcessUserTimeLimit",ctypes.c_longlong),("PerJobUserTimeLimit",ctypes.c_longlong),("LimitFlags",wintypes.DWORD),("MinimumWorkingSetSize",ctypes.c_size_t),("MaximumWorkingSetSize",ctypes.c_size_t),("ActiveProcessLimit",wintypes.DWORD),("Affinity",ctypes.c_size_t),("PriorityClass",wintypes.DWORD),("SchedulingClass",wintypes.DWORD)]

class EXTENDED_LIMITS(ctypes.Structure):
    _fields_=[("BasicLimitInformation",BASIC_LIMITS),("IoInfo",IO_COUNTERS),("ProcessMemoryLimit",ctypes.c_size_t),("JobMemoryLimit",ctypes.c_size_t),("PeakProcessMemoryUsed",ctypes.c_size_t),("PeakJobMemoryUsed",ctypes.c_size_t)]

class THREADENTRY32(ctypes.Structure):
    _fields_=[("dwSize",wintypes.DWORD),("cntUsage",wintypes.DWORD),("th32ThreadID",wintypes.DWORD),("th32OwnerProcessID",wintypes.DWORD),("tpBasePri",wintypes.LONG),("tpDeltaPri",wintypes.LONG),("dwFlags",wintypes.DWORD)]

class WindowsJob:
    def __init__(self):
        self.kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        k=self.kernel
        declarations={
            "CreateJobObjectW":([ctypes.c_void_p,wintypes.LPCWSTR],wintypes.HANDLE),
            "SetInformationJobObject":([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD],wintypes.BOOL),
            "AssignProcessToJobObject":([wintypes.HANDLE,wintypes.HANDLE],wintypes.BOOL),
            "TerminateJobObject":([wintypes.HANDLE,wintypes.UINT],wintypes.BOOL),
            "CloseHandle":([wintypes.HANDLE],wintypes.BOOL),
            "CreateToolhelp32Snapshot":([wintypes.DWORD,wintypes.DWORD],wintypes.HANDLE),
            "Thread32First":([wintypes.HANDLE,ctypes.POINTER(THREADENTRY32)],wintypes.BOOL),
            "Thread32Next":([wintypes.HANDLE,ctypes.POINTER(THREADENTRY32)],wintypes.BOOL),
            "OpenThread":([wintypes.DWORD,wintypes.BOOL,wintypes.DWORD],wintypes.HANDLE),
            "ResumeThread":([wintypes.HANDLE],wintypes.DWORD),
        }
        for name,(args,result) in declarations.items():
            fn=getattr(k,name); fn.argtypes=args; fn.restype=result
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        limits=EXTENDED_LIMITS(); limits.BasicLimitInformation.LimitFlags=0x2000
        if not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            error=ctypes.WinError(ctypes.get_last_error()); self.close(); raise error

    def attach_and_resume(self,process):
        k=self.kernel
        if not k.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot=k.CreateToolhelp32Snapshot(0x00000004,0)
        if snapshot==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
        entry=THREADENTRY32(); entry.dwSize=ctypes.sizeof(entry)
        try:
            found=k.Thread32First(snapshot,ctypes.byref(entry))
            while found:
                if entry.th32OwnerProcessID==process.pid:
                    thread=k.OpenThread(0x0002,False,entry.th32ThreadID)
                    if not thread: raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if k.ResumeThread(thread)==0xFFFFFFFF: raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally: k.CloseHandle(thread)
                found=k.Thread32Next(snapshot,ctypes.byref(entry))
            raise OSError("cannot find the suspended child initial thread")
        finally: k.CloseHandle(snapshot)

    def terminate(self):
        if self.handle: self.kernel.TerminateJobObject(self.handle,1)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle=None
