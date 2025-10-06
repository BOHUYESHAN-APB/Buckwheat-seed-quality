class BuckwheatSeedSortingSystem {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        
        // 系统状态
        this.isRunning = true;
        this.processSpeed = 1.0;
        this.seedFlow = 20; // 每秒种子数量
        this.currentMode = 'feeding';
        
        // 种子分类定义 - 基于项目文档
        this.seedCategories = {
            'seeda': { 
                name: 'A级', 
                quality: '籽粒饱满、无破损、无霉变', 
                color: 0x27ae60, 
                use: '荞麦苗菜培育（核心原料）' 
            },
            'seedb': { 
                name: 'B级', 
                quality: '籽粒完整、饱满度一般、无霉变', 
                color: 0xf39c12, 
                use: '常规农业种植/人类食用加工' 
            },
            'seedc': { 
                name: 'C级', 
                quality: '籽粒轻微破损、无霉变', 
                color: 0xe67e22, 
                use: '饲料加工/农产品深加工' 
            },
            'seedd': { 
                name: 'D级', 
                quality: '含杂质、破损严重或霉变', 
                color: 0xe74c3c, 
                use: '直接丢弃（无利用价值）' 
            }
        };
        
        // 实时统计
        this.statistics = {
            totalProcessed: 0,
            seeda: 0,
            seedb: 0,
            seedc: 0,
            seedd: 0
        };
        
        // 3D对象数组
        this.seeds = [];
        this.impurities = [];
        this.machines = [];
        
        // 动画计时器
        this.lastSeedTime = 0;
        this.animationId = null;
        
        // 初始化外壳可见性
        this.casingVisible = true;
        
        this.init();
    }
    
    init() {
        this.createScene();
        this.createCamera();
        this.createRenderer();
        this.createControls();
        this.createLights();
        this.createMachineStructure();
        this.createEnvironment();
        this.setupEventListeners();
        this.animate();
        
        document.getElementById('loading').style.display = 'none';
    }
    
    createScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf0f0f0);
        this.scene.fog = new THREE.Fog(0xf0f0f0, 50, 200);
    }
    
    createCamera() {
        this.camera = new THREE.PerspectiveCamera(
            75, 
            window.innerWidth / window.innerHeight, 
            0.1, 
            1000
        );
        this.camera.position.set(0, 40, 80);
    }
    
    createRenderer() {
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        document.getElementById('container').appendChild(this.renderer.domElement);
    }
    
    createControls() {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.enableZoom = true;
        this.controls.enablePan = true;
        this.controls.maxDistance = 150;
        this.controls.minDistance = 20;
    }
    
    createLights() {
        // 环境光
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        
        // 主光源
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(50, 100, 50);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        // 工作区域照明
        const workLight1 = new THREE.SpotLight(0xffffff, 0.8, 50, Math.PI / 6, 0.5);
        workLight1.position.set(0, 50, 0);
        workLight1.target.position.set(0, 0, 0);
        this.scene.add(workLight1);
        this.scene.add(workLight1.target);
    }
    
    createSeedGeometry() {
        // 创建真实的荞麦种子形状 - 三角锥形，更符合实际荞麦种子形状
        const geometry = new THREE.ConeGeometry(0.5, 1.2, 3);
        geometry.scale(1.2, 1, 0.8); // 调整为更扁平的三角锥形
        
        // 添加一些随机变形，使种子看起来更自然
        const positions = geometry.attributes.position;
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i);
            const y = positions.getY(i);
            const z = positions.getZ(i);
            
            // 添加轻微的随机变形
            positions.setX(i, x * (1 + (Math.random() - 0.5) * 0.1));
            positions.setY(i, y * (1 + (Math.random() - 0.5) * 0.1));
            positions.setZ(i, z * (1 + (Math.random() - 0.5) * 0.1));
        }
        
        positions.needsUpdate = true;
        geometry.computeVertexNormals();
        
        return geometry;
    }
    
    createMachineStructure() {
        // 1. 进料模块 - 整体性优化设计，更符合实际物理结构
        const feedModuleGroup = new THREE.Group();
        
        // 进料斗主体 - 漏斗形状，更符合实际设计
        const feederTopGeometry = new THREE.CylinderGeometry(10, 8, 5, 32);
        const feederMaterial = new THREE.MeshPhongMaterial({ color: 0x7f8c8d });
        const feederTop = new THREE.Mesh(feederTopGeometry, feederMaterial);
        feederTop.position.set(0, 45, 0);
        feedModuleGroup.add(feederTop);
        
        // 进料斗中段 - 锥形过渡
        const feederMidGeometry = new THREE.CylinderGeometry(8, 5, 10, 32);
        const feederMid = new THREE.Mesh(feederMidGeometry, feederMaterial);
        feederMid.position.set(0, 37.5, 0);
        feedModuleGroup.add(feederMid);
        
        // 进料斗下段 - 更窄的锥形
        const feederBottomGeometry = new THREE.CylinderGeometry(5, 2, 10, 32);
        const feederBottom = new THREE.Mesh(feederBottomGeometry, feederMaterial);
        feederBottom.position.set(0, 27.5, 0);
        feedModuleGroup.add(feederBottom);
        
        // 进料斗底部开口 - 合理大小的圆形开口
        const openingGeometry = new THREE.CylinderGeometry(1.5, 1.5, 1, 16);
        const openingMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const opening = new THREE.Mesh(openingGeometry, openingMaterial);
        opening.position.set(0, 22, 0);
        feedModuleGroup.add(opening);
        
        // 进料斗支撑结构
        const supportGeometry = new THREE.CylinderGeometry(0.5, 0.5, 20);
        const supportMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        
        // 四个支撑柱
        const supportPositions = [
            { x: 8, z: 8 },
            { x: 8, z: -8 },
            { x: -8, z: 8 },
            { x: -8, z: -8 }
        ];
        
        supportPositions.forEach(pos => {
            const support = new THREE.Mesh(supportGeometry, supportMaterial);
            support.position.set(pos.x, 35, pos.z);
            feedModuleGroup.add(support);
        });
        
        // 进料斗顶部边缘 - 防止种子溢出
        const rimGeometry = new THREE.TorusGeometry(10, 0.5, 8, 32);
        const rimMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        const rim = new THREE.Mesh(rimGeometry, rimMaterial);
        rim.position.set(0, 47.5, 0);
        rim.rotation.x = Math.PI / 2;
        feedModuleGroup.add(rim);
        
        // 进料斗标签
        const feederLabelGeometry = new THREE.PlaneGeometry(6, 1.5);
        const feederCanvas = document.createElement('canvas');
        feederCanvas.width = 256;
        feederCanvas.height = 64;
        const feederContext = feederCanvas.getContext('2d');
        feederContext.fillStyle = '#7f8c8d';
        feederContext.fillRect(0, 0, 256, 64);
        feederContext.fillStyle = 'white';
        feederContext.font = 'bold 20px Arial';
        feederContext.textAlign = 'center';
        feederContext.fillText('进料斗', 128, 40);
        
        const feederLabelTexture = new THREE.CanvasTexture(feederCanvas);
        const feederLabelMaterial = new THREE.MeshBasicMaterial({ map: feederLabelTexture });
        const feederLabel = new THREE.Mesh(feederLabelGeometry, feederLabelMaterial);
        feederLabel.position.set(0, 50, 10.1);
        feedModuleGroup.add(feederLabel);
        
        // 添加振动平板 - 新增结构，用于接收从进料斗落下的种子
        const vibratingPlateGeometry = new THREE.BoxGeometry(30, 1, 20);
        const vibratingPlateMaterial = new THREE.MeshPhongMaterial({ color: 0x7f8c8d });
        const vibratingPlate = new THREE.Mesh(vibratingPlateGeometry, vibratingPlateMaterial);
        vibratingPlate.position.set(0, 20, 0);
        feedModuleGroup.add(vibratingPlate);
        
        // 添加细孔筛 - 位于振动平板上方，用于筛选种子
        const sieveGeometry = new THREE.BoxGeometry(28, 0.5, 18);
        const sieveMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x95a5a6,
            transparent: true,
            opacity: 0.8
        });
        const sieve = new THREE.Mesh(sieveGeometry, sieveMaterial);
        sieve.position.set(0, 20.75, 0);
        feedModuleGroup.add(sieve);
        
        // 在细孔筛上添加小孔，模拟筛网效果
        const holeRadius = 0.3;
        const holeSpacing = 1.5;
        for (let x = -12; x <= 12; x += holeSpacing) {
            for (let z = -8; z <= 8; z += holeSpacing) {
                const holeGeometry = new THREE.CylinderGeometry(holeRadius, holeRadius, 0.6);
                const holeMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
                const hole = new THREE.Mesh(holeGeometry, holeMaterial);
                hole.position.set(x, 20.75, z);
                feedModuleGroup.add(hole);
            }
        }
        
        // 振动平板支撑结构
        const plateSupportGeometry = new THREE.BoxGeometry(1, 8, 1);
        const plateSupportMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        
        // 四个支撑柱
        const plateSupportPositions = [
            { x: 14, z: 9 },
            { x: 14, z: -9 },
            { x: -14, z: 9 },
            { x: -14, z: -9 }
        ];
        
        plateSupportPositions.forEach(pos => {
            const plateSupport = new THREE.Mesh(plateSupportGeometry, plateSupportMaterial);
            plateSupport.position.set(pos.x, 16, pos.z);
            feedModuleGroup.add(plateSupport);
        });
        
        // 细孔筛标签
        const sieveLabelGeometry = new THREE.PlaneGeometry(6, 1.5);
        const sieveCanvas = document.createElement('canvas');
        sieveCanvas.width = 256;
        sieveCanvas.height = 64;
        const sieveContext = sieveCanvas.getContext('2d');
        sieveContext.fillStyle = '#95a5a6';
        sieveContext.fillRect(0, 0, 256, 64);
        sieveContext.fillStyle = 'white';
        sieveContext.font = 'bold 20px Arial';
        sieveContext.textAlign = 'center';
        sieveContext.fillText('细孔筛', 128, 40);
        
        const sieveLabelTexture = new THREE.CanvasTexture(sieveCanvas);
        const sieveLabelMaterial = new THREE.MeshBasicMaterial({ map: sieveLabelTexture });
        const sieveLabel = new THREE.Mesh(sieveLabelGeometry, sieveLabelMaterial);
        sieveLabel.position.set(0, 22, 10.1);
        feedModuleGroup.add(sieveLabel);
        
        this.scene.add(feedModuleGroup);
        this.machines.push(feedModuleGroup);
        
        // 2. 杂质分离模块 - 优化风扇位置，改为斜向30度角度吹风
        const impurityGroup = new THREE.Group();
        
        // 农用风格风扇 - 重新设计位置和角度，更符合实际物理结构
        const fanBaseGeometry = new THREE.BoxGeometry(8, 3, 8);
        const fanBaseMaterial = new THREE.MeshPhongMaterial({ color: 0x7f8c8d });
        const fanBase = new THREE.Mesh(fanBaseGeometry, fanBaseMaterial);
        fanBase.position.set(-20, 25, 10); // 调整位置，位于振动平板侧面
        impurityGroup.add(fanBase);
        
        // 风扇罩 - 保护网状结构
        const fanCoverGeometry = new THREE.CylinderGeometry(6, 6, 1, 16);
        const fanCoverMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x95a5a6,
            transparent: true,
            opacity: 0.7,
            wireframe: true
        });
        const fanCover = new THREE.Mesh(fanCoverGeometry, fanCoverMaterial);
        fanCover.position.set(-20, 27, 10);
        fanCover.rotation.z = Math.PI / 2;
        fanCover.rotation.y = Math.PI / 6; // 30度角度
        impurityGroup.add(fanCover);
        
        // 风扇叶片中心
        const fanCenterGeometry = new THREE.CylinderGeometry(1, 1, 0.5, 8);
        const fanCenterMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const fanCenter = new THREE.Mesh(fanCenterGeometry, fanCenterMaterial);
        fanCenter.position.set(-20, 27, 10);
        fanCenter.rotation.z = Math.PI / 2;
        fanCenter.rotation.y = Math.PI / 6; // 30度角度
        impurityGroup.add(fanCenter);
        
        // 风扇叶片（旋转动画）- 调整角度，斜向30度吹风
        const bladeGeometry = new THREE.BoxGeometry(5, 0.3, 1.5);
        const bladeMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        
        for (let i = 0; i < 6; i++) {
            const blade = new THREE.Mesh(bladeGeometry, bladeMaterial);
            blade.position.set(-20, 27, 10);
            blade.rotation.z = (i * Math.PI) / 3;
            blade.rotation.y = Math.PI / 2;
            blade.rotation.x = Math.PI / 6; // 30度角度，斜向吹风
            impurityGroup.add(blade);
            // 存储叶片引用以便后续动画
            if (!this.fanBlades) this.fanBlades = [];
            this.fanBlades.push(blade);
        }
        
        // 风扇支撑柱
        const fanSupportGeometry = new THREE.CylinderGeometry(1.5, 2, 15);
        const fanSupportMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        const fanSupport = new THREE.Mesh(fanSupportGeometry, fanSupportMaterial);
        fanSupport.position.set(-20, 17.5, 10);
        impurityGroup.add(fanSupport);
        
        // 添加第二个风扇，位于另一侧，形成对吹效果
        const fanBase2 = new THREE.Mesh(fanBaseGeometry, fanBaseMaterial);
        fanBase2.position.set(20, 25, 10); // 调整位置，位于振动平板另一侧
        impurityGroup.add(fanBase2);
        
        const fanCover2 = new THREE.Mesh(fanCoverGeometry, fanCoverMaterial);
        fanCover2.position.set(20, 27, 10);
        fanCover2.rotation.z = Math.PI / 2;
        fanCover2.rotation.y = -Math.PI / 6; // -30度角度
        impurityGroup.add(fanCover2);
        
        const fanCenter2 = new THREE.Mesh(fanCenterGeometry, fanCenterMaterial);
        fanCenter2.position.set(20, 27, 10);
        fanCenter2.rotation.z = Math.PI / 2;
        fanCenter2.rotation.y = -Math.PI / 6; // -30度角度
        impurityGroup.add(fanCenter2);
        
        for (let i = 0; i < 6; i++) {
            const blade = new THREE.Mesh(bladeGeometry, bladeMaterial);
            blade.position.set(20, 27, 10);
            blade.rotation.z = (i * Math.PI) / 3;
            blade.rotation.y = Math.PI / 2;
            blade.rotation.x = -Math.PI / 6; // -30度角度，斜向吹风
            impurityGroup.add(blade);
            // 存储叶片引用以便后续动画
            this.fanBlades.push(blade);
        }
        
        const fanSupport2 = new THREE.Mesh(fanSupportGeometry, fanSupportMaterial);
        fanSupport2.position.set(20, 17.5, 10);
        impurityGroup.add(fanSupport2);
        
        // 杂质存储槽 - 优化设计，更符合实际农用机械特点
const impurityBinShape = new THREE.Shape();
const impurityBinWidth = 12;
const impurityBinDepth = 12;
const impurityBinHeight = 8;

// 创建梯形截面，更符合实际存储槽形状
impurityBinShape.moveTo(-impurityBinWidth/2, 0);
impurityBinShape.lineTo(-impurityBinWidth/2 + 1, impurityBinHeight);
impurityBinShape.lineTo(impurityBinWidth/2 - 1, impurityBinHeight);
impurityBinShape.lineTo(impurityBinWidth/2, 0);
impurityBinShape.lineTo(-impurityBinWidth/2, 0);

const impurityBinExtrudeSettings = {
    depth: impurityBinDepth,
    bevelEnabled: true,
    bevelThickness: 0.3,
    bevelSize: 0.3,
    bevelSegments: 2
};

const impurityBinGeometry = new THREE.ExtrudeGeometry(impurityBinShape, impurityBinExtrudeSettings);
const impurityBinMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
const impurityBin = new THREE.Mesh(impurityBinGeometry, impurityBinMaterial);
impurityBin.position.set(-30, 4, 0);
impurityBin.rotation.y = Math.PI / 2; // 调整方向
impurityGroup.add(impurityBin);

// 杂质存储槽底部开口
const impurityBinBottomGeometry = new THREE.BoxGeometry(impurityBinWidth - 2, 0.2, impurityBinDepth - 2);
const impurityBinBottom = new THREE.Mesh(impurityBinBottomGeometry, new THREE.MeshPhongMaterial({ color: 0x222222 }));
impurityBinBottom.position.set(-30, 3.9, 0);
impurityGroup.add(impurityBinBottom);

// 杂质存储槽与风扇之间的连接管道 - 优化路径，避免穿模
const impurityPipeCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-23, 25, 8),
    new THREE.Vector3(-26, 20, 5),
    new THREE.Vector3(-30, 15, 2),
    new THREE.Vector3(-30, 8, 0) // 延伸到存储槽内部
]);

const impurityTubeGeometry = new THREE.TubeGeometry(impurityPipeCurve, 20, 0.6, 8, false);
const impurityTubeMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
const impurityTube = new THREE.Mesh(impurityTubeGeometry, impurityTubeMaterial);
impurityGroup.add(impurityTube);

// 添加杂质管道出口，更符合实际物理结构
const impurityOutletGeometry = new THREE.CylinderGeometry(0.8, 0.6, 1, 16);
const impurityOutlet = new THREE.Mesh(impurityOutletGeometry, impurityTubeMaterial);
impurityOutlet.rotation.z = Math.PI / 2;
impurityOutlet.position.set(-30, 8, 0);
impurityGroup.add(impurityOutlet);
        
        // 杂质存储槽标签
        const impurityLabelGeometry = new THREE.PlaneGeometry(6, 1.5);
        const impurityCanvas = document.createElement('canvas');
        impurityCanvas.width = 256;
        impurityCanvas.height = 64;
        const impurityContext = impurityCanvas.getContext('2d');
        impurityContext.fillStyle = '#5d6d7e';
        impurityContext.fillRect(0, 0, 256, 64);
        impurityContext.fillStyle = 'white';
        impurityContext.font = 'bold 20px Arial';
        impurityContext.textAlign = 'center';
        impurityContext.fillText('杂质存储槽', 128, 40);
        
        const impurityLabelTexture = new THREE.CanvasTexture(impurityCanvas);
        const impurityLabelMaterial = new THREE.MeshBasicMaterial({ map: impurityLabelTexture });
        const impurityLabel = new THREE.Mesh(impurityLabelGeometry, impurityLabelMaterial);
        impurityLabel.position.set(-30, 8, 6.1);
        impurityGroup.add(impurityLabel);
        
        this.scene.add(impurityGroup);
        this.machines.push(impurityGroup);
        
        // 3. 种子输送模块 - 优化V型输送管道，连接振动平板和细孔筛
        const conveyorGroup = new THREE.Group();
        const pipeCount = 8; // 八根并行管道
        const pipeSpacing = 4; // 管道间距
        
        // 创建统一的D级种子收集滑槽 - 优化设计，更符合实际物理结构
        const wasteChuteGeometry = new THREE.BoxGeometry(pipeCount * pipeSpacing + 4, 1, 12);
        const wasteChuteMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
        const wasteChute = new THREE.Mesh(wasteChuteGeometry, wasteChuteMaterial);
        wasteChute.position.set(0, 10, 25); // 调整位置，连接振动平板
        conveyorGroup.add(wasteChute);
        
        // 创建D级种子收集滑槽的侧壁 - 增加高度和倾斜角度
        const sideWallGeometry = new THREE.BoxGeometry(1, 6, 12);
        const leftSideWall = new THREE.Mesh(sideWallGeometry, wasteChuteMaterial);
        leftSideWall.position.set(-(pipeCount * pipeSpacing + 4) / 2 + 0.5, 13, 25);
        leftSideWall.rotation.z = Math.PI / 36; // 轻微倾斜
        conveyorGroup.add(leftSideWall);
        
        const rightSideWall = new THREE.Mesh(sideWallGeometry, wasteChuteMaterial);
        rightSideWall.position.set((pipeCount * pipeSpacing + 4) / 2 - 0.5, 13, 25);
        rightSideWall.rotation.z = -Math.PI / 36; // 轻微倾斜
        conveyorGroup.add(rightSideWall);
        
        // 创建D级种子收集滑槽的后壁
        const backWallGeometry = new THREE.BoxGeometry(pipeCount * pipeSpacing + 4, 6, 1);
        const backWall = new THREE.Mesh(backWallGeometry, wasteChuteMaterial);
        backWall.position.set(0, 13, 19);
        conveyorGroup.add(backWall);
        
        // 创建D级种子收集滑槽的导流板，使种子流向收集仓
        for (let i = 0; i < pipeCount; i++) {
            const xOffset = (i - (pipeCount - 1) / 2) * pipeSpacing;
            
            const guideGeometry = new THREE.BoxGeometry(2, 0.2, 8);
            const guide = new THREE.Mesh(guideGeometry, wasteChuteMaterial);
            guide.position.set(xOffset, 9.5, 21);
            guide.rotation.x = Math.PI / 12; // 向下倾斜
            conveyorGroup.add(guide);
        }
        
        // 创建V型管道 - 优化设计，连接振动平板和细孔筛
        for (let i = 0; i < pipeCount; i++) {
            const pipeGroup = new THREE.Group();
            const xOffset = (i - (pipeCount - 1) / 2) * pipeSpacing;
            
            // V型管道主体 - 优化设计，更符合实际物理结构
            const vShape = new THREE.Shape();
            vShape.moveTo(-1.2, 0);
            vShape.lineTo(0, -2);
            vShape.lineTo(1.2, 0);
            vShape.lineTo(-1.2, 0);
            
            const extrudeSettings = {
                steps: 2,
                depth: 25, // 缩短长度，避免结构过长
                bevelEnabled: true,
                bevelThickness: 0.1,
                bevelSize: 0.1,
                bevelSegments: 1
            };
            
            const pipeGeometry = new THREE.ExtrudeGeometry(vShape, extrudeSettings);
            const pipeMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
            const pipe = new THREE.Mesh(pipeGeometry, pipeMaterial);
            pipe.rotation.x = Math.PI / 2;
            pipe.position.set(xOffset, 15, 5); // 调整位置，连接振动平板
            pipeGroup.add(pipe);
            
            // 添加V型槽内部的导流板，使种子流动更符合物理规律
            const guidePlateGeometry = new THREE.BoxGeometry(0.1, 1.8, 20); // 缩短长度
            const guidePlateMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
            
            // 左侧导流板
            const leftGuidePlate = new THREE.Mesh(guidePlateGeometry, guidePlateMaterial);
            leftGuidePlate.rotation.z = Math.PI / 4;
            leftGuidePlate.position.set(xOffset - 0.6, 14.1, 5);
            pipeGroup.add(leftGuidePlate);
            
            // 右侧导流板
            const rightGuidePlate = new THREE.Mesh(guidePlateGeometry, guidePlateMaterial);
            rightGuidePlate.rotation.z = -Math.PI / 4;
            rightGuidePlate.position.set(xOffset + 0.6, 14.1, 5);
            pipeGroup.add(rightGuidePlate);
            
            // 在V型槽底部添加小孔，用于D级种子掉落
            const holeGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.2);
            const holeMaterial = new THREE.MeshPhongMaterial({ color: 0x1a1a1a });
            
            // 在V型槽中段和末端添加小孔
            for (let z = -5; z <= 15; z += 10) { // 调整位置
                const hole = new THREE.Mesh(holeGeometry, holeMaterial);
                hole.rotation.x = Math.PI / 2;
                hole.position.set(xOffset, 13.8, z);
                pipeGroup.add(hole);
            }
            
            // 管道支撑结构
            const supportGeometry = new THREE.BoxGeometry(0.8, 8, 0.8); // 调整高度
            const supportMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
            
            // 入口支撑
            const entranceSupport = new THREE.Mesh(supportGeometry, supportMaterial);
            entranceSupport.position.set(xOffset, 11, -7); // 调整位置
            pipeGroup.add(entranceSupport);
            
            // 出口支撑
            const exitSupport = new THREE.Mesh(supportGeometry, supportMaterial);
            exitSupport.position.set(xOffset, 11, 17); // 调整位置
            pipeGroup.add(exitSupport);
            
            // 中间支撑
            const middleSupport = new THREE.Mesh(supportGeometry, supportMaterial);
            middleSupport.position.set(xOffset, 11, 5); // 调整位置
            pipeGroup.add(middleSupport);
            
            conveyorGroup.add(pipeGroup);
        }
        
        // V型管道组标签
        const vPipeLabelGeometry = new THREE.PlaneGeometry(6, 1.5);
        const vPipeCanvas = document.createElement('canvas');
        vPipeCanvas.width = 256;
        vPipeCanvas.height = 64;
        const vPipeContext = vPipeCanvas.getContext('2d');
        vPipeContext.fillStyle = '#34495e';
        vPipeContext.fillRect(0, 0, 256, 64);
        vPipeContext.fillStyle = 'white';
        vPipeContext.font = 'bold 20px Arial';
        vPipeContext.textAlign = 'center';
        vPipeContext.fillText('V型输送管道', 128, 40);
        
        const vPipeLabelTexture = new THREE.CanvasTexture(vPipeCanvas);
        const vPipeLabelMaterial = new THREE.MeshBasicMaterial({ map: vPipeLabelTexture });
        const vPipeLabel = new THREE.Mesh(vPipeLabelGeometry, vPipeLabelMaterial);
        vPipeLabel.position.set(0, 18, 25);
        conveyorGroup.add(vPipeLabel);
        
        this.scene.add(conveyorGroup);
        this.machines.push(conveyorGroup);
        
        // 4. 品质检测与分选模块 - 摄像头、检测指示灯和A/B/C级吸料仓
const detectionGroup = new THREE.Group();

// 摄像头支架 - 优化设计，更符合实际物理结构
const cameraStandShape = new THREE.Shape();
const cameraStandWidth = 1;
const cameraStandHeight = 10;

// 创建梯形截面，更符合实际支架形状
cameraStandShape.moveTo(-cameraStandWidth/2, 0);
cameraStandShape.lineTo(-cameraStandWidth/2 + 0.2, cameraStandHeight);
cameraStandShape.lineTo(cameraStandWidth/2 - 0.2, cameraStandHeight);
cameraStandShape.lineTo(cameraStandWidth/2, 0);
cameraStandShape.lineTo(-cameraStandWidth/2, 0);

const cameraStandExtrudeSettings = {
    depth: cameraStandWidth,
    bevelEnabled: true,
    bevelThickness: 0.1,
    bevelSize: 0.1,
    bevelSegments: 1
};

const cameraStandGeometry = new THREE.ExtrudeGeometry(cameraStandShape, cameraStandExtrudeSettings);
const cameraStandMaterial = new THREE.MeshPhongMaterial({ color: 0x5d6d7e });
const cameraStand = new THREE.Mesh(cameraStandGeometry, cameraStandMaterial);
cameraStand.position.set(20, 20, 0);
cameraStand.rotation.y = Math.PI / 2; // 调整方向
detectionGroup.add(cameraStand);

// 摄像头 - 优化设计，更符合实际物理结构
const cameraBodyGeometry = new THREE.BoxGeometry(2.5, 2, 3.5);
const cameraMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
const cameraBody = new THREE.Mesh(cameraBodyGeometry, cameraMaterial);
cameraBody.position.set(20, 30, 0);
detectionGroup.add(cameraBody);

// 摄像头镜头
const cameraLensGeometry = new THREE.CylinderGeometry(0.8, 0.6, 0.5, 16);
const cameraLensMaterial = new THREE.MeshPhongMaterial({ 
    color: 0x1a1a1a,
    shininess: 100
});
const cameraLens = new THREE.Mesh(cameraLensGeometry, cameraLensMaterial);
cameraLens.rotation.z = Math.PI / 2;
cameraLens.position.set(21.5, 30, 0);
detectionGroup.add(cameraLens);

// 检测指示灯 - 优化设计，更符合实际物理结构
const lightBaseGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.2, 16);
const lightBaseMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
const lightBase = new THREE.Mesh(lightBaseGeometry, lightBaseMaterial);
lightBase.position.set(20, 31.5, 0);
detectionGroup.add(lightBase);

const lightGeometry = new THREE.SphereGeometry(0.5, 16, 16);
const lightMaterial = new THREE.MeshPhongMaterial({ 
    color: 0xe74c3c,
    emissive: 0xe74c3c,
    emissiveIntensity: 0.5
});
const light = new THREE.Mesh(lightGeometry, lightMaterial);
light.position.set(20, 32, 0);
detectionGroup.add(light);

// 添加摄像头支架，更符合实际物理结构
const cameraSupportGeometry = new THREE.BoxGeometry(0.5, 5, 0.5);
const cameraSupport = new THREE.Mesh(cameraSupportGeometry, cameraStandMaterial);
cameraSupport.position.set(20, 25, 0);
detectionGroup.add(cameraSupport);

// 为每个V型槽创建A/B/C级吸料仓和管道
const suctionPipes = [];
const suctionLabels = ['A级吸料', 'B级吸料', 'C级吸料'];
const suctionColors = [0x27ae60, 0xf39c12, 0x3498db];

// 为每个V型槽创建三根吸料管
for (let v = 0; v < 8; v++) {
    const vPosition = -14 + v * 4; // V型槽的X轴位置
    
    for (let i = 0; i < 3; i++) {
        // 吸料仓 - 位于V型槽上方，优化设计更符合实际物理结构
const suctionBinShape = new THREE.Shape();
const suctionBinWidth = 1.5;
const suctionBinDepth = 1.5;
const suctionBinHeight = 1.5;

// 创建梯形截面，更符合实际吸料仓形状
suctionBinShape.moveTo(-suctionBinWidth/2, 0);
suctionBinShape.lineTo(-suctionBinWidth/2 + 0.1, suctionBinHeight);
suctionBinShape.lineTo(suctionBinWidth/2 - 0.1, suctionBinHeight);
suctionBinShape.lineTo(suctionBinWidth/2, 0);
suctionBinShape.lineTo(-suctionBinWidth/2, 0);

const suctionBinExtrudeSettings = {
    depth: suctionBinDepth,
    bevelEnabled: true,
    bevelThickness: 0.1,
    bevelSize: 0.1,
    bevelSegments: 1
};

const suctionBinGeometry = new THREE.ExtrudeGeometry(suctionBinShape, suctionBinExtrudeSettings);
const suctionBinMaterial = new THREE.MeshPhongMaterial({ color: suctionColors[i] });
const suctionBin = new THREE.Mesh(suctionBinGeometry, suctionBinMaterial);
suctionBin.position.set(vPosition, 25, -2 - i * 1.5);
suctionBin.rotation.y = Math.PI / 2; // 调整方向
detectionGroup.add(suctionBin);

// 吸料仓底部开口
const suctionBinBottomGeometry = new THREE.BoxGeometry(suctionBinWidth - 0.3, 0.1, suctionBinDepth - 0.3);
const suctionBinBottom = new THREE.Mesh(suctionBinBottomGeometry, new THREE.MeshPhongMaterial({ color: 0x222222 }));
suctionBinBottom.position.set(vPosition, 24.9, -2 - i * 1.5);
detectionGroup.add(suctionBinBottom);
        
        // 吸料管 - 从吸料仓到V型槽上方，优化设计更符合实际物理结构
        const pipeCurve = new THREE.CatmullRomCurve3([
            new THREE.Vector3(vPosition, 25, -2 - i * 1.5),
            new THREE.Vector3(vPosition, 22, -1),
            new THREE.Vector3(vPosition, 20, 0),
            new THREE.Vector3(vPosition, 19.5, 0.5) // 调整管道长度，避免穿模
        ]);
        
        const tubeGeometry = new THREE.TubeGeometry(pipeCurve, 20, 0.3, 8, false); // 减小管道半径
        const tubeMaterial = new THREE.MeshPhongMaterial({ color: suctionColors[i] });
        const tube = new THREE.Mesh(tubeGeometry, tubeMaterial);
        detectionGroup.add(tube);
        
        // 添加吸料口，更符合实际物理结构
        const suctionHeadGeometry = new THREE.CylinderGeometry(0.5, 0.3, 0.8, 16); // 减小吸料口尺寸
        const suctionHead = new THREE.Mesh(suctionHeadGeometry, tubeMaterial);
        suctionHead.rotation.x = Math.PI / 2;
        suctionHead.position.set(vPosition, 19.5, 0.5); // 调整位置，避免穿模
        detectionGroup.add(suctionHead);
        
        // 存储管道引用以便后续使用
        if (!suctionPipes[v]) suctionPipes[v] = [];
        suctionPipes[v][i] = {
            bin: suctionBin,
            tube: tube,
            type: ['A', 'B', 'C'][i]
        };
    }
}

// 存储吸料管道引用
this.suctionPipes = suctionPipes;
        
        this.scene.add(detectionGroup);
        this.machines.push(detectionGroup);
        
        // 5. 成品收纳模块 - A/B/C/D级收纳仓
const collectionGroup = new THREE.Group();

// A/B/C级收纳仓 - 位置调整以适应新的分选系统
const binPositions = [
    { pos: [-20, 5, 15], grade: 'A', color: 0x27ae60 },
    { pos: [0, 5, 15], grade: 'B', color: 0xf39c12 },
    { pos: [20, 5, 15], grade: 'C', color: 0x3498db }
];

binPositions.forEach(bin => {
    // 收纳仓主体 - 优化设计更符合实际物理结构
    const binShape = new THREE.Shape();
    const binWidth = 8;
    const binDepth = 8;
    const binHeight = 10;
    
    // 创建梯形截面，更符合实际收纳仓形状
    binShape.moveTo(-binWidth/2, 0);
    binShape.lineTo(-binWidth/2 + 0.5, binHeight);
    binShape.lineTo(binWidth/2 - 0.5, binHeight);
    binShape.lineTo(binWidth/2, 0);
    binShape.lineTo(-binWidth/2, 0);
    
    const extrudeSettings = {
        depth: binDepth,
        bevelEnabled: true,
        bevelThickness: 0.2,
        bevelSize: 0.2,
        bevelSegments: 2
    };
    
    const binGeometry = new THREE.ExtrudeGeometry(binShape, extrudeSettings);
    const binMaterial = new THREE.MeshPhongMaterial({ color: bin.color });
    const binBox = new THREE.Mesh(binGeometry, binMaterial);
    binBox.position.set(bin.pos[0], bin.pos[1], bin.pos[2]);
    binBox.rotation.y = Math.PI / 2; // 调整方向
    collectionGroup.add(binBox);
    
    // 收纳仓底部开口
    const binBottomGeometry = new THREE.BoxGeometry(binWidth - 1, 0.2, binDepth - 1);
    const binBottom = new THREE.Mesh(binBottomGeometry, new THREE.MeshPhongMaterial({ color: 0x222222 }));
    binBottom.position.set(bin.pos[0], bin.pos[1] - 0.1, bin.pos[2]);
    collectionGroup.add(binBottom);
    
    // 收纳仓标签
    const labelGeometry = new THREE.PlaneGeometry(4, 1.5);
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 96;
    const context = canvas.getContext('2d');
    context.fillStyle = `#${bin.color.toString(16).padStart(6, '0')}`;
    context.fillRect(0, 0, 256, 96);
    context.fillStyle = 'white';
    context.font = 'bold 24px Arial';
    context.textAlign = 'center';
    context.fillText(`${bin.grade}级种子收纳仓`, 128, 56);
    
    const labelTexture = new THREE.CanvasTexture(canvas);
    const labelMaterial = new THREE.MeshBasicMaterial({ map: labelTexture });
    const label = new THREE.Mesh(labelGeometry, labelMaterial);
    label.position.set(bin.pos[0], bin.pos[1] + 5.5, bin.pos[2] + 4.1);
    collectionGroup.add(label);
    
    // 从吸料仓到收纳仓的汇总管道 - 优化设计，避免穿模和结构过长
    const pipeCurve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(bin.pos[0], 20, 0),
        new THREE.Vector3(bin.pos[0], 15, 5),
        new THREE.Vector3(bin.pos[0], 10, bin.pos[2] - 4),
        new THREE.Vector3(bin.pos[0], bin.pos[1] + 5, bin.pos[2] - 1) // 调整管道末端位置，避免穿模
    ]);
    
    const tubeGeometry = new THREE.TubeGeometry(pipeCurve, 20, 0.4, 8, false); // 减小管道半径
    const tubeMaterial = new THREE.MeshPhongMaterial({ color: bin.color });
    const tube = new THREE.Mesh(tubeGeometry, tubeMaterial);
    collectionGroup.add(tube);
    
    // 添加管道出口，更符合实际物理结构
    const outletGeometry = new THREE.CylinderGeometry(0.5, 0.4, 0.8, 16); // 减小出口尺寸
    const outlet = new THREE.Mesh(outletGeometry, tubeMaterial);
    outlet.rotation.z = Math.PI / 2;
    outlet.position.set(bin.pos[0], bin.pos[1] + 5, bin.pos[2] - 1); // 调整位置，避免穿模
    collectionGroup.add(outlet);
});

// D级种子收纳仓 - 位置在V型槽末端统一滑槽下方，优化设计更符合实际物理结构
const dBinShape = new THREE.Shape();
const dBinWidth = 36;
const dBinDepth = 12;
const dBinHeight = 8;

// 创建梯形截面，更符合实际收纳仓形状
dBinShape.moveTo(-dBinWidth/2, 0);
dBinShape.lineTo(-dBinWidth/2 + 1, dBinHeight);
dBinShape.lineTo(dBinWidth/2 - 1, dBinHeight);
dBinShape.lineTo(dBinWidth/2, 0);
dBinShape.lineTo(-dBinWidth/2, 0);

const dExtrudeSettings = {
    depth: dBinDepth,
    bevelEnabled: true,
    bevelThickness: 0.3,
    bevelSize: 0.3,
    bevelSegments: 2
};

const dBinGeometry = new THREE.ExtrudeGeometry(dBinShape, dExtrudeSettings);
const dBinMaterial = new THREE.MeshPhongMaterial({ color: 0x95a5a6 });
const dBin = new THREE.Mesh(dBinGeometry, dBinMaterial);
dBin.position.set(0, 0, 15);
dBin.rotation.y = Math.PI / 2; // 调整方向
collectionGroup.add(dBin);

// D级收纳仓底部开口
const dBinBottomGeometry = new THREE.BoxGeometry(dBinWidth - 2, 0.2, dBinDepth - 2);
const dBinBottom = new THREE.Mesh(dBinBottomGeometry, new THREE.MeshPhongMaterial({ color: 0x222222 }));
dBinBottom.position.set(0, -0.1, 15);
collectionGroup.add(dBinBottom);

// D级收纳仓标签
const dLabelGeometry = new THREE.PlaneGeometry(8, 2);
const dCanvas = document.createElement('canvas');
dCanvas.width = 256;
dCanvas.height = 64;
const dContext = dCanvas.getContext('2d');
dContext.fillStyle = '#95a5a6';
dContext.fillRect(0, 0, 256, 64);
dContext.fillStyle = 'white';
dContext.font = 'bold 24px Arial';
dContext.textAlign = 'center';
dContext.fillText('D级种子收纳仓', 128, 40);

const dLabelTexture = new THREE.CanvasTexture(dCanvas);
const dLabelMaterial = new THREE.MeshBasicMaterial({ map: dLabelTexture });
const dLabel = new THREE.Mesh(dLabelGeometry, dLabelMaterial);
dLabel.position.set(0, 4, 21);
collectionGroup.add(dLabel);

// 从统一滑槽到D级收纳仓的管道 - 优化设计，避免穿模和结构过长
const dPipeCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 8, 8),
    new THREE.Vector3(0, 5, 10),
    new THREE.Vector3(0, 2, 13),
    new THREE.Vector3(0, 1, 14) // 调整管道末端位置，避免穿模
]);

const dTubeGeometry = new THREE.TubeGeometry(dPipeCurve, 20, 0.6, 8, false); // 减小管道半径
const dTubeMaterial = new THREE.MeshPhongMaterial({ color: 0x95a5a6 });
const dTube = new THREE.Mesh(dTubeGeometry, dTubeMaterial);
collectionGroup.add(dTube);

// 添加D级管道出口，更符合实际物理结构
const dOutletGeometry = new THREE.CylinderGeometry(0.8, 0.6, 1.2, 16); // 减小出口尺寸
const dOutlet = new THREE.Mesh(dOutletGeometry, dTubeMaterial);
dOutlet.rotation.z = Math.PI / 2;
dOutlet.position.set(0, 1, 14); // 调整位置，避免穿模
collectionGroup.add(dOutlet);

this.scene.add(collectionGroup);
        this.machines.push(collectionGroup);
        
        // 6. 可隐藏的仪器外壳
        this.createMachineCasing();
        
        // 保存外壳引用
        this.machineCasing = this.casingGroup;
    }
    
    createMachineCasing() {
        // 创建可隐藏的仪器外壳组
        this.casingGroup = new THREE.Group();
        
        // 外壳材质 - 半透明以显示内部结构
        const casingMaterial = new THREE.MeshPhongMaterial({ 
            color: 0xecf0f1,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        
        // 顶部外壳 - 优化设计，添加通风口
const topCasingGeometry = new THREE.BoxGeometry(80, 2, 50);
const topCasing = new THREE.Mesh(topCasingGeometry, casingMaterial);
topCasing.position.set(0, 45, 0);
this.casingGroup.add(topCasing);

// 顶部通风口 - 更符合实际物理结构
for (let x = -30; x <= 30; x += 15) {
    for (let z = -20; z <= 20; z += 15) {
        const ventGeometry = new THREE.BoxGeometry(8, 0.5, 8);
        const ventMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const vent = new THREE.Mesh(ventGeometry, ventMaterial);
        vent.position.set(x, 45.8, z);
        this.casingGroup.add(vent);
        
        // 通风口格栅
        const gridGeometry = new THREE.BoxGeometry(8, 0.1, 0.5);
        const gridMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
        
        for (let i = -3; i <= 3; i++) {
            const grid = new THREE.Mesh(gridGeometry, gridMaterial);
            grid.position.set(x + i, 46.1, z);
            this.casingGroup.add(grid);
        }
    }
}
        
        // 左侧外壳 - 优化设计，添加通风口
const leftCasingGeometry = new THREE.BoxGeometry(2, 50, 50);
const leftCasing = new THREE.Mesh(leftCasingGeometry, casingMaterial);
leftCasing.position.set(-40, 20, 0);
this.casingGroup.add(leftCasing);

// 左侧通风口 - 更符合实际物理结构
for (let y = 10; y <= 30; y += 10) {
    for (let z = -15; z <= 15; z += 15) {
        const ventGeometry = new THREE.BoxGeometry(0.5, 6, 8);
        const ventMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const vent = new THREE.Mesh(ventGeometry, ventMaterial);
        vent.position.set(-40.8, y, z);
        this.casingGroup.add(vent);
        
        // 通风口格栅
        const gridGeometry = new THREE.BoxGeometry(0.1, 6, 0.5);
        const gridMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
        
        for (let i = -3; i <= 3; i++) {
            const grid = new THREE.Mesh(gridGeometry, gridMaterial);
            grid.position.set(-40.9, y, z + i);
            this.casingGroup.add(grid);
        }
    }
}
        
        // 右侧外壳 - 优化设计，添加通风口
const rightCasingGeometry = new THREE.BoxGeometry(2, 50, 50);
const rightCasing = new THREE.Mesh(rightCasingGeometry, casingMaterial);
rightCasing.position.set(40, 20, 0);
this.casingGroup.add(rightCasing);

// 右侧通风口 - 更符合实际物理结构
for (let y = 10; y <= 30; y += 10) {
    for (let z = -15; z <= 15; z += 15) {
        const ventGeometry = new THREE.BoxGeometry(0.5, 6, 8);
        const ventMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const vent = new THREE.Mesh(ventGeometry, ventMaterial);
        vent.position.set(40.8, y, z);
        this.casingGroup.add(vent);
        
        // 通风口格栅
        const gridGeometry = new THREE.BoxGeometry(0.1, 6, 0.5);
        const gridMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
        
        for (let i = -3; i <= 3; i++) {
            const grid = new THREE.Mesh(gridGeometry, gridMaterial);
            grid.position.set(40.9, y, z + i);
            this.casingGroup.add(grid);
        }
    }
}
        
        // 后侧外壳 - 优化设计，添加通风口
const backCasingGeometry = new THREE.BoxGeometry(80, 50, 2);
const backCasing = new THREE.Mesh(backCasingGeometry, casingMaterial);
backCasing.position.set(0, 20, -25);
this.casingGroup.add(backCasing);

// 后侧通风口 - 更符合实际物理结构
for (let x = -30; x <= 30; x += 15) {
    for (let y = 10; y <= 30; y += 10) {
        const ventGeometry = new THREE.BoxGeometry(8, 6, 0.5);
        const ventMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        const vent = new THREE.Mesh(ventGeometry, ventMaterial);
        vent.position.set(x, y, -25.8);
        this.casingGroup.add(vent);
        
        // 通风口格栅
        const gridGeometry = new THREE.BoxGeometry(0.5, 6, 0.1);
        const gridMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
        
        for (let i = -3; i <= 3; i++) {
            const grid = new THREE.Mesh(gridGeometry, gridMaterial);
            grid.position.set(x + i, y, -25.9);
            this.casingGroup.add(grid);
        }
    }
}
        
        // 前侧外壳 - 分为两部分以便观察内部
        const frontLeftCasingGeometry = new THREE.BoxGeometry(35, 50, 2);
        const frontLeftCasing = new THREE.Mesh(frontLeftCasingGeometry, casingMaterial);
        frontLeftCasing.position.set(-22.5, 20, 25);
        this.casingGroup.add(frontLeftCasing);
        
        const frontRightCasingGeometry = new THREE.BoxGeometry(35, 50, 2);
        const frontRightCasing = new THREE.Mesh(frontRightCasingGeometry, casingMaterial);
        frontRightCasing.position.set(22.5, 20, 25);
        this.casingGroup.add(frontRightCasing);
        
        // 底部外壳
        const bottomCasingGeometry = new THREE.BoxGeometry(80, 2, 50);
        const bottomCasing = new THREE.Mesh(bottomCasingGeometry, casingMaterial);
        bottomCasing.position.set(0, -2, 0);
        this.casingGroup.add(bottomCasing);
        
        // 外壳框架 - 更坚固的结构感
        const frameMaterial = new THREE.MeshPhongMaterial({ color: 0x34495e });
        
        // 顶部框架
        const topFrameGeometry = new THREE.BoxGeometry(82, 1, 52);
        const topFrame = new THREE.Mesh(topFrameGeometry, frameMaterial);
        topFrame.position.set(0, 46, 0);
        this.casingGroup.add(topFrame);
        
        // 底部框架
        const bottomFrameGeometry = new THREE.BoxGeometry(82, 1, 52);
        const bottomFrame = new THREE.Mesh(bottomFrameGeometry, frameMaterial);
        bottomFrame.position.set(0, -3, 0);
        this.casingGroup.add(bottomFrame);
        
        // 左侧框架
        const leftFrameGeometry = new THREE.BoxGeometry(1, 52, 52);
        const leftFrame = new THREE.Mesh(leftFrameGeometry, frameMaterial);
        leftFrame.position.set(-41, 20, 0);
        this.casingGroup.add(leftFrame);
        
        // 右侧框架
        const rightFrameGeometry = new THREE.BoxGeometry(1, 52, 52);
        const rightFrame = new THREE.Mesh(rightFrameGeometry, frameMaterial);
        rightFrame.position.set(41, 20, 0);
        this.casingGroup.add(rightFrame);
        
        // 后侧框架
        const backFrameGeometry = new THREE.BoxGeometry(82, 52, 1);
        const backFrame = new THREE.Mesh(backFrameGeometry, frameMaterial);
        backFrame.position.set(0, 20, -26);
        this.casingGroup.add(backFrame);
        
        // 前侧框架 - 分为两部分
        const frontLeftFrameGeometry = new THREE.BoxGeometry(37, 52, 1);
        const frontLeftFrame = new THREE.Mesh(frontLeftFrameGeometry, frameMaterial);
        frontLeftFrame.position.set(-22.5, 20, 26);
        this.casingGroup.add(frontLeftFrame);
        
        const frontRightFrameGeometry = new THREE.BoxGeometry(37, 52, 1);
        const frontRightFrame = new THREE.Mesh(frontRightFrameGeometry, frameMaterial);
        frontRightFrame.position.set(22.5, 20, 26);
        this.casingGroup.add(frontRightFrame);
        
        // 控制面板外壳 - 优化设计，更符合实际物理结构
const controlPanelShape = new THREE.Shape();
const controlPanelWidth = 10;
const controlPanelHeight = 15;

// 创建圆角矩形，更符合实际控制面板形状
const cornerRadius = 1;
controlPanelShape.moveTo(-controlPanelWidth/2 + cornerRadius, -controlPanelHeight/2);
controlPanelShape.lineTo(controlPanelWidth/2 - cornerRadius, -controlPanelHeight/2);
controlPanelShape.quadraticCurveTo(controlPanelWidth/2, -controlPanelHeight/2, controlPanelWidth/2, -controlPanelHeight/2 + cornerRadius);
controlPanelShape.lineTo(controlPanelWidth/2, controlPanelHeight/2 - cornerRadius);
controlPanelShape.quadraticCurveTo(controlPanelWidth/2, controlPanelHeight/2, controlPanelWidth/2 - cornerRadius, controlPanelHeight/2);
controlPanelShape.lineTo(-controlPanelWidth/2 + cornerRadius, controlPanelHeight/2);
controlPanelShape.quadraticCurveTo(-controlPanelWidth/2, controlPanelHeight/2, -controlPanelWidth/2, controlPanelHeight/2 - cornerRadius);
controlPanelShape.lineTo(-controlPanelWidth/2, -controlPanelHeight/2 + cornerRadius);
controlPanelShape.quadraticCurveTo(-controlPanelWidth/2, -controlPanelHeight/2, -controlPanelWidth/2 + cornerRadius, -controlPanelHeight/2);

const controlPanelExtrudeSettings = {
    depth: 1,
    bevelEnabled: true,
    bevelThickness: 0.2,
    bevelSize: 0.2,
    bevelSegments: 2
};

const controlPanelGeometry = new THREE.ExtrudeGeometry(controlPanelShape, controlPanelExtrudeSettings);
const controlPanelMaterial = new THREE.MeshPhongMaterial({ color: 0x2c3e50 });
const controlPanel = new THREE.Mesh(controlPanelGeometry, controlPanelMaterial);
controlPanel.position.set(0, 25, 26);
this.casingGroup.add(controlPanel);

// 控制面板显示屏
const screenGeometry = new THREE.BoxGeometry(6, 4, 0.1);
const screenMaterial = new THREE.MeshPhongMaterial({ 
    color: 0x000000,
    emissive: 0x001122,
    emissiveIntensity: 0.2
});
const screen = new THREE.Mesh(screenGeometry, screenMaterial);
screen.position.set(0, 27, 26.6);
this.casingGroup.add(screen);

// 控制面板按钮
const buttonGeometry = new THREE.CylinderGeometry(0.5, 0.5, 0.2, 16);
const buttonMaterial = new THREE.MeshPhongMaterial({ color: 0xe74c3c });

// 电源按钮
const powerButton = new THREE.Mesh(buttonGeometry, buttonMaterial);
powerButton.position.set(-3, 22, 26.6);
this.casingGroup.add(powerButton);

// 控制按钮
const controlButton = new THREE.Mesh(buttonGeometry, new THREE.MeshPhongMaterial({ color: 0x3498db }));
controlButton.position.set(3, 22, 26.6);
this.casingGroup.add(controlButton);
        
        // 控制面板标签
        const panelLabelGeometry = new THREE.PlaneGeometry(6, 2);
        const panelCanvas = document.createElement('canvas');
        panelCanvas.width = 256;
        panelCanvas.height = 64;
        const panelContext = panelCanvas.getContext('2d');
        panelContext.fillStyle = '#2c3e50';
        panelContext.fillRect(0, 0, 256, 64);
        panelContext.fillStyle = 'white';
        panelContext.font = 'bold 20px Arial';
        panelContext.textAlign = 'center';
        panelContext.fillText('控制面板', 128, 40);
        
        const panelLabelTexture = new THREE.CanvasTexture(panelCanvas);
        const panelLabelMaterial = new THREE.MeshBasicMaterial({ map: panelLabelTexture });
        const panelLabel = new THREE.Mesh(panelLabelGeometry, panelLabelMaterial);
        panelLabel.position.set(0, 33, 27);
        this.casingGroup.add(panelLabel);
        
        // 外壳可见性状态
        this.casingVisible = true;
        
        // 添加到场景
        this.scene.add(this.casingGroup);
        this.machines.push(this.casingGroup);
    }
    
    toggleCasing() {
        // 切换外壳可见性
        if (this.machineCasing) {
            this.casingVisible = !this.casingVisible;
            this.machineCasing.visible = this.casingVisible;
            
            // 更新按钮文本
            const toggleCasingBtn = document.getElementById('toggle-casing-btn');
            if (toggleCasingBtn) {
                toggleCasingBtn.textContent = this.casingVisible ? '隐藏外壳' : '显示外壳';
            }
        }
    }
    
    createEnvironment() {
        // 地面
        const groundGeometry = new THREE.PlaneGeometry(200, 200);
        const groundMaterial = new THREE.MeshLambertMaterial({ 
            color: 0xe0e0e0,
            transparent: true,
            opacity: 0.8
        });
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = 0;
        ground.receiveShadow = true;
        this.scene.add(ground);
        
        // 网格
        const gridHelper = new THREE.GridHelper(200, 20, 0xcccccc, 0xdddddd);
        gridHelper.position.y = 0.01;
        this.scene.add(gridHelper);
        
        // 背景墙
        const wallGeometry = new THREE.BoxGeometry(200, 100, 1);
        const wallMaterial = new THREE.MeshLambertMaterial({ color: 0xf5f5f5 });
        const backWall = new THREE.Mesh(wallGeometry, wallMaterial);
        backWall.position.set(0, 50, -50);
        this.scene.add(backWall);
        
        // 侧墙
        const sideWallGeometry = new THREE.BoxGeometry(1, 100, 200);
        const leftWall = new THREE.Mesh(sideWallGeometry, wallMaterial);
        leftWall.position.set(-100, 50, 0);
        this.scene.add(leftWall);
        
        const rightWall = new THREE.Mesh(sideWallGeometry, wallMaterial);
        rightWall.position.set(100, 50, 0);
        this.scene.add(rightWall);
    }
    
    createSeed(category, position) {
        const geometry = this.createSeedGeometry();
        const material = new THREE.MeshPhongMaterial({ 
            color: this.seedCategories[category].color,
            shininess: 30,
            transparent: true,
            opacity: 0.9
        });
        
        const seed = new THREE.Mesh(geometry, material);
        seed.position.copy(position);
        seed.castShadow = true;
        seed.receiveShadow = true;
        
        seed.userData = {
            category: category,
            phase: 'feeding', // feeding, impurityRemoval, conveying, detecting, sorting, collecting
            speed: 0.1 + Math.random() * 0.1,
            detectionTime: 0,
            targetBin: this.getTargetBin(category),
            rotationSpeed: {
                x: (Math.random() - 0.5) * 0.02,
                y: (Math.random() - 0.5) * 0.02,
                z: (Math.random() - 0.5) * 0.02
            },
            pipeIndex: Math.floor(Math.random() * 3) // 随机选择一个管道
        };
        
        this.scene.add(seed);
        this.seeds.push(seed);
        
        return seed;
    }
    
    createImpurity(position) {
        // 创建杂质（叶片、碎屑等）- 更符合实际物理结构
        const impurityType = Math.random() > 0.5 ? 'leaf' : 'debris';
        
        let geometry, material;
        
        if (impurityType === 'leaf') {
            // 叶片形状 - 更符合实际的叶片形状
            geometry = new THREE.Shape();
            geometry.moveTo(0, 0);
            geometry.bezierCurveTo(0.5, 0.2, 0.8, 0.5, 1, 1);
            geometry.bezierCurveTo(0.8, 1.2, 0.5, 1.3, 0, 1.5);
            geometry.bezierCurveTo(-0.5, 1.3, -0.8, 1.2, -1, 1);
            geometry.bezierCurveTo(-0.8, 0.5, -0.5, 0.2, 0, 0);
            
            const extrudeSettings = {
                depth: 0.05,
                bevelEnabled: true,
                bevelThickness: 0.02,
                bevelSize: 0.02,
                bevelSegments: 2
            };
            
            geometry = new THREE.ExtrudeGeometry(geometry, extrudeSettings);
            material = new THREE.MeshLambertMaterial({ 
                color: 0x2ecc71,
                transparent: true,
                opacity: 0.7,
                side: THREE.DoubleSide
            });
        } else {
            // 碎屑形状 - 不规则形状
            geometry = new THREE.DodecahedronGeometry(0.5, 0);
            
            // 添加随机变形，使碎屑看起来更自然
            const positions = geometry.attributes.position;
            for (let i = 0; i < positions.count; i++) {
                const x = positions.getX(i);
                const y = positions.getY(i);
                const z = positions.getZ(i);
                
                // 添加随机变形
                positions.setX(i, x * (1 + (Math.random() - 0.5) * 0.3));
                positions.setY(i, y * (1 + (Math.random() - 0.5) * 0.3));
                positions.setZ(i, z * (1 + (Math.random() - 0.5) * 0.3));
            }
            
            positions.needsUpdate = true;
            geometry.computeVertexNormals();
            
            material = new THREE.MeshLambertMaterial({ 
                color: 0x8b4513,
                transparent: true,
                opacity: 0.7
            });
        }
        
        const impurity = new THREE.Mesh(geometry, material);
        impurity.position.copy(position);
        
        // 随机旋转，使杂质看起来更自然
        impurity.rotation.x = Math.random() * Math.PI;
        impurity.rotation.y = Math.random() * Math.PI;
        impurity.rotation.z = Math.random() * Math.PI;
        
        impurity.userData = {
            type: impurityType,
            speed: 0.05 + Math.random() * 0.05,
            direction: new THREE.Vector3(
                -1, // 向杂质存储槽方向移动
                Math.random() * 0.5,
                (Math.random() - 0.5) * 0.5
            ),
            rotationSpeed: {
                x: (Math.random() - 0.5) * 0.02,
                y: (Math.random() - 0.5) * 0.02,
                z: (Math.random() - 0.5) * 0.02
            }
        };
        
        this.scene.add(impurity);
        this.impurities.push(impurity);
        
        return impurity;
    }
    
    getTargetBin(category) {
        const binPositions = {
            'seeda': { x: -15, y: 5, z: 25 },
            'seedb': { x: 0, y: 5, z: 25 },
            'seedc': { x: 15, y: 5, z: 25 },
            'seedd': { x: 30, y: 5, z: 25 }
        };
        return binPositions[category];
    }
    
    updateSeeds(deltaTime) {
        this.seeds.forEach((seed, index) => {
            // 旋转动画
            seed.rotation.x += seed.userData.rotationSpeed.x;
            seed.rotation.y += seed.userData.rotationSpeed.y;
            seed.rotation.z += seed.userData.rotationSpeed.z;
            
            // 根据阶段更新位置和行为
            switch (seed.userData.phase) {
                case 'feeding':
                    this.updateFeedingPhase(seed, deltaTime);
                    break;
                case 'impurityRemoval':
                    this.updateImpurityRemovalPhase(seed, deltaTime);
                    break;
                case 'conveying':
                    this.updateConveyingPhase(seed, deltaTime);
                    break;
                case 'detecting':
                    this.updateDetectingPhase(seed, deltaTime);
                    break;
                case 'sorting':
                    this.updateSortingPhase(seed, deltaTime);
                    break;
                case 'collecting':
                    this.updateCollectingPhase(seed, deltaTime);
                    break;
            }
        });
        
        // 更新杂质
        this.impurities.forEach((impurity, index) => {
            impurity.position.add(impurity.userData.direction.clone().multiplyScalar(impurity.userData.speed * deltaTime));
            
            // 添加旋转动画
            impurity.rotation.x += impurity.userData.rotationSpeed.x;
            impurity.rotation.y += impurity.userData.rotationSpeed.y;
            impurity.rotation.z += impurity.userData.rotationSpeed.z;
            
            // 如果杂质飞出视野或到达存储槽，移除它
            if (impurity.position.x < -30 || impurity.position.length() > 50) {
                this.scene.remove(impurity);
                this.impurities.splice(index, 1);
            }
        });
        
        // 更新风扇叶片旋转
        if (this.fanBlades) {
            this.fanBlades.forEach(blade => {
                blade.rotation.z += 0.1 * this.processSpeed;
            });
        }
    }
    
    updateFeedingPhase(seed, deltaTime) {
        // 种子从进料斗下落
        if (seed.position.y > 25) {
            seed.position.y -= seed.userData.speed * deltaTime * 10;
        } else {
            // 进入杂质分离阶段
            seed.userData.phase = 'impurityRemoval';
            
            // 有一定概率产生杂质
            if (Math.random() < 0.1 && seed.userData.category === 'seedd') {
                this.createImpurity(seed.position.clone());
            }
        }
    }
    
    updateImpurityRemovalPhase(seed, deltaTime) {
        // 在杂质分离区域，种子继续下落，杂质被吹走
        if (seed.position.y > 20) {
            seed.position.y -= seed.userData.speed * deltaTime * 10;
            
            // 轻微的水平移动，模拟气流影响
            seed.position.x += (Math.random() - 0.5) * 0.1;
            seed.position.z += (Math.random() - 0.5) * 0.1;
        } else {
            // 进入输送阶段
            seed.userData.phase = 'conveying';
            
            // 根据管道索引设置初始位置
            const pipePositions = [-6, 0, 6];
            seed.position.x = pipePositions[seed.userData.pipeIndex];
            seed.position.z = -18; // 管道入口位置
        }
    }
    
    updateConveyingPhase(seed, deltaTime) {
        // 在V型管道中滑动
        const pipeLength = 36; // 管道长度
        const currentZ = seed.position.z + 18; // 相对于管道入口的位置
        
        if (currentZ < pipeLength) {
            // 沿管道滑动
            seed.position.z += seed.userData.speed * deltaTime * 5;
            
            // 轻微震动
            seed.position.y = 20 + Math.sin(Date.now() * 0.01) * 0.2;
            
            // 检测点在管道中段（约2/3处）
            if (currentZ > pipeLength * 0.6 && currentZ < pipeLength * 0.7) {
                seed.userData.phase = 'detecting';
                seed.userData.detectionTime = 0;
            }
        } else {
            // 如果没有经过检测，直接进入分选阶段
            if (seed.userData.phase !== 'detecting') {
                seed.userData.phase = 'sorting';
            }
        }
    }
    
    updateDetectingPhase(seed, deltaTime) {
        // 在检测区域停留
        seed.userData.detectionTime += deltaTime;
        
        // 轻微震动
        seed.position.y = 20 + Math.sin(Date.now() * 0.01) * 0.2;
        
        // 检测时间结束，进入分选阶段
        if (seed.userData.detectionTime > 1) {
            seed.userData.phase = 'sorting';
        }
    }
    
    updateSortingPhase(seed, deltaTime) {
        // 根据类别分选到不同的收集仓
        const target = seed.userData.targetBin;
        const direction = new THREE.Vector3(
            target.x - seed.position.x,
            target.y - seed.position.y,
            target.z - seed.position.z
        ).normalize();
        
        // D级种子没有吸料仓，继续沿管道滑动
        if (seed.userData.category === 'seedd') {
            seed.position.z += seed.userData.speed * deltaTime * 5;
            
            // 检查是否到达管道末端
            if (seed.position.z > 18) {
                seed.userData.phase = 'collecting';
                this.updateStatistics(seed.userData.category);
            }
        } else {
            // A/B/C级种子被吸料仓吸取
            seed.position.add(direction.multiplyScalar(seed.userData.speed * deltaTime * 15));
            
            // 检查是否到达目标仓
            const distance = seed.position.distanceTo(new THREE.Vector3(target.x, target.y, target.z));
            if (distance < 3) {
                seed.userData.phase = 'collecting';
                this.updateStatistics(seed.userData.category);
            }
        }
    }
    
    updateCollectingPhase(seed, deltaTime) {
        // 在收集仓中堆积
        const target = seed.userData.targetBin;
        seed.position.y = Math.max(target.y + 2, seed.position.y - deltaTime * 2);
        
        // 添加一些随机运动
        seed.position.x += (Math.random() - 0.5) * 0.1;
        seed.position.z += (Math.random() - 0.5) * 0.1;
    }
    
    updateStatistics(category) {
        this.statistics.totalProcessed++;
        this.statistics[category]++;
        this.updateUI();
    }
    
    updateUI() {
        document.getElementById('totalProcessed').textContent = this.statistics.totalProcessed;
        document.getElementById('countA').textContent = this.statistics.seeda;
        document.getElementById('countB').textContent = this.statistics.seedb;
        document.getElementById('countC').textContent = this.statistics.seedc;
        document.getElementById('countD').textContent = this.statistics.seedd;
        
        // 更新进度条
        const total = this.statistics.totalProcessed || 1;
        document.getElementById('progressA').style.width = (this.statistics.seeda / total * 100) + '%';
        document.getElementById('progressB').style.width = (this.statistics.seedb / total * 100) + '%';
        document.getElementById('progressC').style.width = (this.statistics.seedc / total * 100) + '%';
        document.getElementById('progressD').style.width = (this.statistics.seedd / total * 100) + '%';
    }
    
    setupEventListeners() {
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // 控制面板事件
        document.getElementById('processSpeed').addEventListener('input', (e) => {
            this.processSpeed = parseFloat(e.target.value);
            document.getElementById('speedValue').textContent = this.processSpeed.toFixed(1) + 'x';
        });
        
        document.getElementById('seedFlow').addEventListener('input', (e) => {
            this.seedFlow = parseInt(e.target.value);
            document.getElementById('flowValue').textContent = this.seedFlow;
        });
        
        // 系统控制按钮
        const toggleSystemBtn = document.getElementById('toggle-system-btn');
        const resetSystemBtn = document.getElementById('reset-system-btn');
        const loadDatasetBtn = document.getElementById('load-dataset-btn');
        const toggleCasingBtn = document.getElementById('toggle-casing-btn');
        
        if (toggleSystemBtn) {
            toggleSystemBtn.addEventListener('click', () => {
                this.toggleSystem();
            });
        }
        
        if (resetSystemBtn) {
            resetSystemBtn.addEventListener('click', () => {
                this.resetSystem();
            });
        }
        
        if (loadDatasetBtn) {
            loadDatasetBtn.addEventListener('click', () => {
                this.loadDataset();
            });
        }
        
        if (toggleCasingBtn) {
            toggleCasingBtn.addEventListener('click', () => {
                this.toggleCasing();
            });
        }
        
        // 键盘事件
        document.addEventListener('keydown', (e) => {
            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    this.toggleSystem();
                    break;
                case 'r':
                    this.resetSystem();
                    break;
                case 'l':
                    this.loadDataset();
                    break;
                case 'c':
                    this.toggleCasing();
                    break;
            }
        });
    }
    
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        
        const currentTime = Date.now();
        const deltaTime = Math.min((currentTime - (this.lastTime || currentTime)) / 1000, 0.1);
        this.lastTime = currentTime;
        
        if (this.isRunning) {
            // 生成新种子
            if (currentTime - this.lastSeedTime > 1000 / this.seedFlow) {
                this.generateSeed();
                this.lastSeedTime = currentTime;
            }
            
            // 更新种子位置
            this.updateSeeds(deltaTime);
        }
        
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
    
    generateSeed() {
        // 随机选择种子类别，按照实际分布概率
        const categories = ['seeda', 'seedb', 'seedc', 'seedd'];
        const weights = [0.4, 0.3, 0.2, 0.1]; // A、B、C、D级的概率分布
        
        let randomValue = Math.random();
        let selectedCategory = 'seeda';
        
        for (let i = 0; i < weights.length; i++) {
            randomValue -= weights[i];
            if (randomValue <= 0) {
                selectedCategory = categories[i];
                break;
            }
        }
        
        // 在进料斗顶部生成种子
        const position = new THREE.Vector3(
            (Math.random() - 0.5) * 5,
            48,
            (Math.random() - 0.5) * 5
        );
        
        this.createSeed(selectedCategory, position);
    }
    
    // 系统控制方法
    toggleSystem() {
        this.isRunning = !this.isRunning;
    }
    
    resetSystem() {
        // 清除所有种子和杂质
        this.seeds.forEach(seed => {
            this.scene.remove(seed);
        });
        this.seeds = [];
        
        this.impurities.forEach(impurity => {
            this.scene.remove(impurity);
        });
        this.impurities = [];
        
        // 重置统计
        this.statistics = {
            totalProcessed: 0,
            seeda: 0,
            seedb: 0,
            seedc: 0,
            seedd: 0
        };
        
        this.updateUI();
    }
    
    loadDataset() {
        // 模拟加载数据集
        this.resetSystem();
        
        // 显示加载提示
        const loadingElement = document.getElementById('loading');
        loadingElement.style.display = 'block';
        loadingElement.innerHTML = '<div>🌾 正在加载荞麦种子数据集...</div>';
        
        // 模拟加载过程
        setTimeout(() => {
            loadingElement.style.display = 'none';
            
            // 生成一批初始种子
            for (let i = 0; i < 20; i++) {
                setTimeout(() => {
                    this.generateSeed();
                }, i * 100);
            }
        }, 2000);
    }
    
    toggleCasing() {
        // 切换外壳可见性
        if (this.machineCasing) {
            this.casingVisible = !this.casingVisible;
            this.machineCasing.visible = this.casingVisible;
            
            // 更新按钮文本
            const toggleCasingBtn = document.getElementById('toggle-casing-btn');
            if (toggleCasingBtn) {
                toggleCasingBtn.textContent = this.casingVisible ? '隐藏外壳' : '显示外壳';
            }
        }
    }
}

// 演示场景切换函数
function showFeedingProcess() {
    // 更新按钮状态
    document.getElementById('btnFeeding').classList.add('active');
    document.getElementById('btnDetection').classList.remove('active');
    document.getElementById('btnCollection').classList.remove('active');
    
    // 切换到进料场景
    if (window.buckwheatSystem) {
        window.buckwheatSystem.currentMode = 'feeding';
    }
}

function showDetectionProcess() {
    // 更新按钮状态
    document.getElementById('btnFeeding').classList.remove('active');
    document.getElementById('btnDetection').classList.add('active');
    document.getElementById('btnCollection').classList.remove('active');
    
    // 切换到检测场景
    if (window.buckwheatSystem) {
        window.buckwheatSystem.currentMode = 'detection';
    }
}

function showCollectionProcess() {
    // 更新按钮状态
    document.getElementById('btnFeeding').classList.remove('active');
    document.getElementById('btnDetection').classList.remove('active');
    document.getElementById('btnCollection').classList.add('active');
    
    // 切换到收集场景
    if (window.buckwheatSystem) {
        window.buckwheatSystem.currentMode = 'collection';
    }
}

// 系统控制函数
function toggleSystem() {
    if (window.buckwheatSystem) {
        window.buckwheatSystem.toggleSystem();
    }
}

function resetSystem() {
    if (window.buckwheatSystem) {
        window.buckwheatSystem.resetSystem();
    }
}

function loadDataset() {
    if (window.buckwheatSystem) {
        window.buckwheatSystem.loadDataset();
    }
}

function toggleCasing() {
    if (window.buckwheatSystem) {
        window.buckwheatSystem.toggleCasing();
    }
}

// 初始化系统
document.addEventListener('DOMContentLoaded', () => {
    window.buckwheatSystem = new BuckwheatSeedSortingSystem();
});