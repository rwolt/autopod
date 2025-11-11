# Manual Test Plan: V1.2 Network Volume Support

## Prerequisites

- Valid RunPod API key configured
- At least one RunPod network volume created
- Get your volume ID from RunPod UI: https://www.runpod.io/console/user/storage

## Test 1.13: Create pod with --volume-id flag

### Steps:
```bash
# Get your volume ID from RunPod UI
VOLUME_ID="your-volume-id-here"

# Create pod with volume attached
autopod connect --volume-id $VOLUME_ID --gpu "RTX A40"
```

### Expected Results:
- ✓ Pod configuration shows: `Volume: {volume_id} → /workspace`
- ✓ Volume datacenter auto-detected if not specified
- ✓ Warning if datacenter mismatch (volume in different DC than pod)
- ✓ Pod creates successfully
- ✓ No errors about volume not found

### Validation:
Check RunPod UI to verify:
- Pod shows volume attached in console
- Volume appears in pod's storage section

---

## Test 1.14: SSH into pod and verify volume mounted

### Steps:
```bash
# SSH into the newly created pod
autopod ssh

# Inside pod, check if volume is mounted
ls -la /workspace
df -h | grep workspace

# Check mount point
mount | grep workspace

# Try to write/read from volume
echo "test" > /workspace/test.txt
cat /workspace/test.txt
```

### Expected Results:
- ✓ /workspace directory exists
- ✓ Volume shows in df output with correct size
- ✓ Can write files to /workspace
- ✓ Files persist (not ephemeral container storage)

### Common Issues:
- **Mount point not found**: Volume may not have attached (datacenter mismatch?)
- **Permission denied**: Check volume permissions in RunPod UI
- **Empty directory**: Volume attached but may be new/empty

---

## Test 1.15: Verify volume info in autopod info

### Steps:
```bash
# Get pod ID from previous test
POD_ID="your-pod-id"

# Check pod info
autopod info $POD_ID
```

### Expected Results:
- ✓ Panel displays volume information
- ✓ Shows: `Volume: {volume_id} → /workspace`
- ✓ Volume info persists after terminal restart
- ✓ Volume info shows even after pod stop/start

### Validation:
```bash
# Stop pod
autopod stop $POD_ID

# Check info again - volume should still be displayed
autopod info $POD_ID

# Start pod
autopod start $POD_ID

# Check info - volume still there
autopod info $POD_ID
```

---

## Test 1.16 (Optional): Default volume from config

### Setup:
```bash
# Edit config
nano ~/.autopod/config.json

# Add to runpod section:
{
  "providers": {
    "runpod": {
      ...
      "default_volume_id": "your-volume-id",
      "default_volume_mount": "/workspace"
    }
  }
}
```

### Steps:
```bash
# Create pod WITHOUT --volume-id flag
autopod connect --gpu "RTX A40"
```

### Expected Results:
- ✓ Pod automatically uses default_volume_id from config
- ✓ Volume shown in pod configuration
- ✓ Volume attached to pod

---

## Test 1.17 (Optional): CLI flag overrides config

### Steps:
```bash
# With default_volume_id in config, override with different volume
autopod connect --volume-id different-volume-id --gpu "RTX A40"
```

### Expected Results:
- ✓ CLI flag takes precedence over config default
- ✓ different-volume-id is used, not config default
- ✓ Pod configuration shows correct volume

---

## Cleanup

After testing, remember to terminate test pods:
```bash
autopod kill $POD_ID
```

---

## Success Criteria

All tests pass when:
- [x] Task 1.13: Pod creates with volume attached
- [x] Task 1.14: Volume accessible at /workspace in pod
- [x] Task 1.15: Volume info displays in `autopod info`
- [ ] No errors or warnings (except expected datacenter mismatch warning)
- [ ] Volume data persists across pod stop/start
- [ ] Config defaults work as expected

---

## Troubleshooting

### Volume not found error
- Verify volume ID is correct (check RunPod UI)
- Ensure API key has access to the volume

### Datacenter mismatch warning
- Expected if volume is in different datacenter than pod
- Solution: Specify datacenter matching volume's location:
  ```bash
  autopod connect --volume-id abc --datacenter US-GA-1
  ```

### Volume not mounted in pod
- Check RunPod UI to verify volume actually attached
- Try recreating pod
- Verify mount path is correct

### Volume shows in info but not accessible
- Volume attached but may be permissions issue
- Check RunPod pod logs for mount errors
