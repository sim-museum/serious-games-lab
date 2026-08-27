from PIL import Image
import numpy as np, sys, math

def fit(path, label, dump=None):
    im=Image.open(path).convert('RGB'); a=np.asarray(im).astype(int)
    H,W,_=a.shape; R,G,B=a[:,:,0],a[:,:,1],a[:,:,2]
    yy,xx=np.mgrid[0:H,0:W]
    # 1) badge = wheel hub. Yellow, near the horizontal centre, lower half.
    bz=(np.abs(xx-W/2)<0.10*W)&(yy>0.40*H)&(yy<0.97*H)
    bm=(G-B>35)&(R-B>45)&(R>120)&(G>100)&bz
    if bm.sum()<25: return dict(label=label, err='badge not found (%d px)'%bm.sum())
    bys,bxs=np.nonzero(bm); bx,by=float(np.median(bxs)),float(np.median(bys))
    # 2) rim = red, ANYWHERE (no zone gate) — the ellipse fit rejects outliers by radius consistency
    red=(R>80)&(R-G>30)&(R-B>30)
    rmax=0.60*W
    # 3) radial scan from the hub: outermost red pixel per angle
    rs={}; step=2.0
    for deg in range(0,360,3):
        th=math.radians(deg); cx,sy=math.cos(th),math.sin(th)
        last=None; r=6.0
        while r<rmax:
            X=int(round(bx+cx*r)); Y=int(round(by+sy*r))
            if X<0 or Y<0 or X>=W or Y>=H: break
            if red[Y,X]: last=r
            r+=step
        if last is not None: rs[deg]=last
    if len(rs)<40: return dict(label=label, err='too few rim rays (%d)'%len(rs))
    # 4) least-squares ellipse (axis-aligned): r(th)^-2 = cos^2/a^2 + sin^2/b^2
    ths=np.array([math.radians(d) for d in rs]); rr=np.array([rs[d] for d in rs])
    # robust: drop rays whose radius is a wild outlier vs the local median
    med=np.median(rr); keep=(rr>0.45*med)&(rr<1.9*med)
    ths,rr=ths[keep],rr[keep]
    A=np.stack([np.cos(ths)**2, np.sin(ths)**2],axis=1)
    sol,*_=np.linalg.lstsq(A, 1.0/rr**2, rcond=None)
    if sol[0]<=0 or sol[1]<=0: return dict(label=label, err='degenerate ellipse')
    aa=1/math.sqrt(sol[0]); bb=1/math.sqrt(sol[1])
    if dump:
        vis=np.asarray(im).copy(); vis[red]=[0,255,0]
        for d,r in rs.items():
            th=math.radians(d); X=int(bx+math.cos(th)*r); Y=int(by+math.sin(th)*r)
            if 0<=X<W and 0<=Y<H: vis[max(0,Y-2):Y+3, max(0,X-2):X+3]=[255,0,0]
        vis[max(0,int(by)-4):int(by)+5, max(0,int(bx)-4):int(bx)+5]=[255,0,255]
        Image.fromarray(vis.astype('uint8')).save(dump)
    return dict(label=label, W=W, H=H, hub=(bx,by), a=aa, b=bb,
                width_frac=2*aa/W, tilt=bb/aa, rays=len(rr))

if __name__=='__main__':
    for spec in sys.argv[1:]:
        p,l = spec.split('=',1)
        d=fit(p,l, dump=p.replace('.ppm','_fit.png').replace('.png','_fit.png'))
        if 'err' in d: print('  %-20s ERROR: %s'%(d['label'],d['err']))
        else: print('  %-20s wheel width=%.3f of W   b/a=%.3f   (a=%.0f b=%.0f, %d rays)'
                    %(d['label'],d['width_frac'],d['tilt'],d['a'],d['b'],d['rays']))
