# Reports this Windows laptop's hardware; does not download or select a model.
$computer = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
[PSCustomObject]@{ RAM_GB = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1); Available_RAM_GB = [math]::Round($os.FreePhysicalMemory / 1MB, 1) }
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID, @{Name='Free_GB';Expression={[math]::Round($_.FreeSpace / 1GB, 1)}}

Get-CimInstance Win32_Processor | Select-Object @{Name='CPU';Expression={$_.Name}}
Get-CimInstance Win32_VideoController | Select-Object @{Name='GPU';Expression={$_.Name}}
